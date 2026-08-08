#!/usr/bin/env bash
# bluez_config.sh — dono ÚNICO da configuração do BlueZ desta casa.
#
#   bluez_config.sh aplicar     garante FastConnectable=true e
#                               JustWorksRepairing=confirm (install.sh, passo 3d)
#   bluez_config.sh remover     tira TUDO que o `aplicar` põe (uninstall.sh)
#   bluez_config.sh verificar   só LÊ e diz o estado (doctor.sh e bancada)
#   bluez_config.sh podar       apaga backup antigo — SÓ quando ela pede, e por
#                               padrão apenas SIMULA (--dry-run)
#
# POR QUE ESTE ARQUIVO EXISTE (RADIO-ABERTO-01/E1-bis, 06/08/2026)
# ---------------------------------------------------------------
# A lógica morava dentro do `install.sh` e do `uninstall.sh`, e por isso NUNCA
# foi testada: todo portão da suíte lia os dois scripts como TEXTO. O defeito
# que isso escondeu foi MEDIDO na máquina dela em 06/08/2026:
#
#   /etc/bluetooth/main.conf:25 = `JustWorksRepairing=always`
#
# dentro do bloco `# >>> hefesto bluetooth >>>` — ou seja, escrito por uma
# versão ANTERIOR deste próprio projeto. Os assets passaram para `confirm` em
# 05/08 (sprint RADIO-ABERTO-01) e o valor perigoso continuou no disco porque
# a única coisa que reescreve o arquivo é uma execução do `install.sh`, que não
# houve entre as duas datas. A cura estava escrita e não chegava à máquina.
#
# Com o mecanismo aqui fora, a bancada (tests/unit/test_bluez_config_sh.py)
# roda `aplicar`/`remover` contra uma RAIZ FALSA — nada em /etc é tocado — e
# consegue afirmar o que nenhum teste de texto conseguia: que um valor inseguro
# preexistente vira `confirm`, que rodar duas vezes não gera backup novo, e que
# o `remover` devolve o arquivo sem chave nossa.
#
# AS TRÊS INVARIANTES QUE NÃO SE NEGOCIAM
# ---------------------------------------
# 1. NUNCA reiniciar o `bluetoothd` — derrubaria os controles BT conectados
#    (provado ao vivo em 2026-07-17). Toda mudança daqui vale no próximo
#    start do serviço (boot ou restart natural), e isso é dito na tela.
# 2. Arquivo de config que já existia no disco NÃO é reescrito nem apagado sem
#    backup: `cmp` primeiro (mudança real?), backup depois, e a mudança em
#    seguida. Vale para o `/etc/bluetooth/main.conf`, que é conffile do dpkg, e
#    vale IGUAL para os drop-ins de `main.conf.d/` — ver a exceção declarada
#    logo abaixo.
#
#    ATÉ 06/08/2026 A INVARIANTE MENTIA SOBRE O PRÓPRIO ARQUIVO (achado MEDIDO,
#    correção de decisão gravada): ela dizia só `main.conf`, e o caminho dos
#    drop-ins fazia `install -Dm644` por cima — sem `cmp`, sem backup, sem uma
#    palavra — e `rm -f` no `remover`, também sem backup. Um
#    `main.conf.d/hefesto-justworks.conf` editado à mão era destruído SEM CÓPIA
#    NENHUMA enquanto a mesma função imprimia "drop-ins de main.conf.d gravados"
#    como sucesso. Não era regressão (o código inline antigo do install fazia
#    igual), mas este arquivo passou a se declarar DONO ÚNICO, e dono único que
#    enuncia invariante e a viola num dos dois caminhos é pior que dono nenhum.
#
#    A EXCEÇÃO, DECLARADA: quando o arquivo no disco é IGUAL byte a byte ao
#    nosso asset, não há backup — não há informação a perder, e o asset está
#    versionado neste repositório. É o mesmo `cmp` que faz o `main.conf` não
#    gerar backup no no-op.
# 3. Config de terceiro não se apaga — se NEUTRALIZA. Uma chave nossa ativa
#    fora do bloco vira comentário com a marca `#hefesto-desativou# `, e o
#    `remover` devolve a linha original. Antes desta versão o `awk` do install
#    APAGAVA a linha e o uninstall nunca a devolvia: instalar e desinstalar era
#    uma operação destrutiva líquida sobre a config de quem já tinha uma.
#
#    AS TRÊS EXCEÇÕES da promessa "o `remover` devolve o arquivo byte a byte"
#    (só a primeira estava declarada até 06/08/2026):
#      (i)   linhas em branco do FIM do arquivo não voltam — é o preço da
#            idempotência, ver `_despir_main_conf`;
#      (ii)  chave nossa (`FastConnectable`/`JustWorksRepairing`) que um terceiro
#            escreveu DENTRO do nosso bloco sai com o bloco e NÃO volta: a faixa
#            inteira é descartada e nenhuma marca é gravada. O `aplicar` avisa
#            quando isso vai acontecer (ver o rebaixamento do `never`);
#      (iii) linha que já começava com o texto literal `#hefesto-desativou# `
#            ANTES de qualquer `aplicar` nosso é DESCOMENTADA pelo `remover` —
#            ele não sabe distinguir a marca que pôs da que encontrou, e ativa
#            uma linha que estava desativada.
#
# A ASSIMETRIA QUE ESTE ARQUIVO FECHA (era o furo estrutural)
# -----------------------------------------------------------
# O `install.sh` decidia entre DOIS caminhos por um único `if -d main.conf.d`:
# com o diretório presente escrevia os drop-ins e RETORNAVA SEM ABRIR o
# `main.conf`. Como o `bluetoothd` desta casa não lê `main.conf.d` (MEDIDO:
# `strings /usr/libexec/bluetooth/bluetoothd` do bluez 5.86 do backport tem
# `%*s/main.conf` e ZERO ocorrências de `main.conf.d`; `dpkg -L bluez` não
# lista o diretório), bastava alguém criar esse diretório para o instalador
# anunciar "JustWorksRepairing via drop-ins" enquanto o `always` seguia vivo no
# `main.conf`. Aqui os dois caminhos são CUMULATIVOS: o `main.conf` é sempre
# normalizado, e os drop-ins entram POR CIMA quando o diretório existe. Os dois
# lugares passam a dizer a mesma coisa, então qualquer que seja o que o BlueZ
# leia, o valor é `confirm`.
#
# Overrides de bancada (em produção ficam todos no padrão):
#   HEFESTO_BT_ETC              raiz da config     (padrão /etc/bluetooth)
#   HEFESTO_BT_ASSETS           assets/bluetooth   (padrão ../assets/bluetooth)
#   HEFESTO_BT_SUDO             prefixo de root    (padrão `sudo`; vazio = sem)
#   HEFESTO_BT_BACKUPS_MANTER   retenção de backup (padrão 10)
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ETC="${HEFESTO_BT_ETC:-/etc/bluetooth}"
ASSETS="${HEFESTO_BT_ASSETS:-${_SCRIPT_DIR}/../assets/bluetooth}"
SUDO="${HEFESTO_BT_SUDO-sudo}"
#: Retenção usada SÓ pelo subcomando `podar`, e `podar` só roda quando alguém
#: digita `podar`. Ver a nota "A PODA NÃO É AUTOMÁTICA" logo abaixo.
BACKUPS_MANTER="${HEFESTO_BT_BACKUPS_MANTER:-10}"

# A PODA NÃO É AUTOMÁTICA — decisão de 06/08/2026, e é uma REVERSÃO
# ---------------------------------------------------------------
# A primeira versão desta entrega podava os backups dentro do `aplicar` e do
# `remover`. MEDIDO por simulação só-leitura do pipeline exato contra o
# /etc/bluetooth dela: a primeira execução de `aplicar` apagaria 27 dos 37
# backups — e entre eles os DOIS pontos de medição do colapso
# "404 linhas -> 3 linhas" (`main.conf.bak.hefesto-1784672963`, 404 linhas,
# 21/07 19:29, e `main.conf.bak.hefesto-1784694261`, 3 linhas, 22/07 01:24)
# que a própria sprint RADIO-ABERTO-01 registra como suspeita EM ABERTO, sem
# cura. Retenção por mtime descarta primeiro o que tem MAIS valor: o estado
# pré-hefesto e o instante do estrago. O gatilho seria o conselho da própria
# ferramenta ("rode ./install.sh"), e a regra desta casa é
# "não se apaga decisão medida".
#
# Hoje: `aplicar`/`remover` só REPORTAM quantos backups há e quanto ocupam. A
# poda é um subcomando explícito, simula por padrão, NUNCA apaga o mais antigo
# e nunca deixa um ESTADO sumir do disco — de cada conteúdo distinto fica sempre
# ao menos uma cópia, mesmo que todas as cópias dele estejam fora da retenção.
# ~100 KB não valem a evidência do único colapso ainda sem explicação.

MAIN_CONF="${ETC}/main.conf"
DROPIN_DIR="${ETC}/main.conf.d"
DROPIN_FAST="${DROPIN_DIR}/hefesto-fastconnectable.conf"
DROPIN_JW="${DROPIN_DIR}/hefesto-justworks.conf"

BLOCO="${ASSETS}/hefesto-bt.block"
ASSET_FAST="${ASSETS}/hefesto-fastconnectable.conf"
ASSET_JW="${ASSETS}/hefesto-justworks.conf"

#: Marca das chaves de TERCEIRO que neutralizamos. Fixa de propósito: se
#: carregasse data, o `cmp` acusaria mudança a cada execução e o passo deixaria
#: de ser idempotente.
MARCA='#hefesto-desativou# '

#: O valor seguro. Uma constante, e não um literal espalhado, para que o
#: verificador e o aplicador não possam divergir.
VALOR_SEGURO='confirm'

#: As sentinelas: bloco unificado de hoje + os dois legados (instalações
#: anteriores a 21/07 tinham um bloco por chave). Um `remover` que só
#: conhecesse o de hoje deixaria os legados para trás.
_RE_ABRE='^# >>> hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>'
_RE_FECHA='^# <<< hefesto (bluetooth|FastConnectable|JustWorksRepairing) <<<'

_diz()  { printf '      %s\n' "$*"; }
_erro() { printf 'bluez_config.sh: %s\n' "$*" >&2; }

# Executa com o prefixo de root configurado (vazio na bancada).
_r() {
    if [[ -n "${SUDO}" ]]; then
        "${SUDO}" "$@"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Lixo em trânsito: o que existe só ENTRE dois passos e nunca deve sobreviver
#
# ACHADO DE 06/08/2026 (MEDIDO): não havia `trap` nenhum. Um kill (ou um
# Ctrl-C) entre o `mktemp` e o `mv` deixava `.main.conf.hefesto-novo.XXXXXX`
# órfão em /etc/bluetooth — no conffile dela, sem ninguém para contar nem
# varrer. O mesmo vale para o arquivo de backup entre o `mktemp` que o cria
# vazio e o `cp` que o preenche: meio backup é pior que backup nenhum, porque
# tem cara de legítimo.
#
# A regra é: quem cria um arquivo em trânsito REGISTRA; quem o promove a
# arquivo definitivo (ou o apaga) o ESQUECE. O que sobrar na lista quando o
# script morrer — por saída normal, por INT, por TERM ou por HUP — é apagado.
_LIXO=()

_lixo_add() { _LIXO+=("$1"); }

_lixo_tirar() {
    local alvo="$1" p
    local -a resta=()
    if [[ "${#_LIXO[@]}" -gt 0 ]]; then
        for p in "${_LIXO[@]}"; do
            [[ "${p}" == "${alvo}" ]] || resta+=("${p}")
        done
    fi
    _LIXO=()
    if [[ "${#resta[@]}" -gt 0 ]]; then
        _LIXO=("${resta[@]}")
    fi
}

_limpar_lixo() {
    local p
    if [[ "${#_LIXO[@]}" -gt 0 ]]; then
        for p in "${_LIXO[@]}"; do
            [[ -e "${p}" ]] || continue
            _r rm -f "${p}" 2>/dev/null || true
        done
    fi
    _LIXO=()
}

trap '_limpar_lixo' EXIT
trap '_limpar_lixo; exit 130' INT
trap '_limpar_lixo; exit 143' TERM HUP

# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

#: Despeja o conteúdo do arquivo, ESCALANDO para root só quando precisa.
#:
#: Antes, três leituras (`_valor_ativo`, `_tem_bloco_nosso` e o `grep` da marca
#: no `remover`) rodavam sem o prefixo `_r`, ao contrário de todo o resto. Com
#: um `main.conf` ilegível para o usuário (modo 600, que é legítimo num arquivo
#: de config de rádio), o `remover` concluía que NÃO havia nada nosso e deixava
#: o bloco no disco — desinstalar não desinstalava. Escalar sempre também é
#: errado: o `verificar` é o modo que o `doctor.sh` consome, e um `sudo` ali
#: viraria pedido de senha num diagnóstico de leitura. Daí o meio-termo: leitura
#: direta quando o arquivo é legível, `_r` só quando não é.
_cat_conf() {
    local arquivo="$1"
    if [[ -r "${arquivo}" ]]; then
        cat "${arquivo}" 2>/dev/null
    else
        _r cat "${arquivo}" 2>/dev/null
    fi
}

#: O arquivo existe mas nem assim conseguimos ler? Então não afirme nada.
_conf_ilegivel() {
    [[ -f "${MAIN_CONF}" ]] || return 1
    _cat_conf "${MAIN_CONF}" >/dev/null 2>&1 && return 1
    return 0
}

#: O leitor da chave, com as regras do GKeyFile — que é o parser REAL do
#: bluetoothd. Imprime `LOCAL<TAB>VALOR` (LOCAL = `dentro` ou `fora` do nosso
#: bloco de sentinelas) ou NADA quando a chave não está ativa em `[General]`.
#:
#: O DEFEITO QUE ISTO CURA (06/08/2026, MEDIDO contra o oráculo GLib.KeyFile):
#: a versão anterior era um `sed | tail -n 1` que varria o arquivo INTEIRO e
#: ignorava o grupo. Num main.conf com
#:
#:     [General]
#:     JustWorksRepairing=always
#:     [Policy]
#:     JustWorksRepairing=confirm
#:
#: o `verificar` respondia `veredito: OK` e o GKeyFile lia `always` — falso
#: negativo do dono único, consumido pelo doctor E pelo ramo `--no-udev` do
#: install. E a regra "o último vence" (o `tail -n 1`) não tinha teste que
#: mordesse: trocar por `head -n 1` deixava a suíte verde.
#:
#: O que foi MEDIDO com o oráculo e está reproduzido aqui, caso a caso:
#:   - `[General]` repetido MERGE, e a última atribuição da chave vence;
#:   - um `[General]` posterior que NÃO redeclara a chave não apaga a anterior;
#:   - grupo fora de `[General]` (ex.: `[Policy]`) NÃO conta;
#:   - o nome do grupo é o texto EXATO entre colchetes (`[General ]` não é
#:     `[General]`), mas espaço em volta do colchete é descartado;
#:   - espaço à esquerda da chave e em volta do `=` é descartado;
#:   - `#` só é comentário no INÍCIO da linha (com espaço antes, ainda é
#:     comentário); `#` no meio do valor FAZ PARTE do valor — por isso
#:     `JustWorksRepairing=confirm # nota` NÃO vale `confirm`, e aqui também não;
#:   - o espaço à DIREITA do valor é preservado pelo GKeyFile, e aqui também;
#:   - CRLF: o GKeyFile DESCARTA o `\r` do fim da linha e mantém os espaços
#:     (MEDIDO em 06/08/2026 contra o oráculo: `JustWorksRepairing=confirm  \r\n`
#:     vale `'confirm  '`, com os dois espaços e sem o CR). O `sub(/\r$/, "")`
#:     abaixo é essa regra. Sem ele o dono lia `confirm\r`, divergia do BlueZ e
#:     ainda EMBARALHAVA a própria mensagem de erro — o CR volta o cursor e a
#:     frase se sobrescreve no terminal dela.
#: A bancada (tests/unit/test_bluez_config_sh.py) confere cada um desses casos
#: contra o GKeyFile de verdade, em vez de reimplementar um terceiro parser.
_ler_chave() {
    local chave="$1" arquivo="$2"
    [[ -f "${arquivo}" ]] || return 0
    _cat_conf "${arquivo}" | awk -v CHAVE="${chave}" \
                                 -v ABRE="${_RE_ABRE}" -v FECHA="${_RE_FECHA}" '
        function apara(s) {
            sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s
        }
        { sub(/\r$/, "") }
        $0 ~ ABRE  { _dentro = 1; next }
        _dentro && $0 ~ FECHA { _dentro = 0; next }
        {
            t = apara($0)
            if (t == "") next
            if (substr(t, 1, 1) == "#") next
            if (t ~ /^\[.*\]$/) { _grupo = substr(t, 2, length(t) - 2); next }
            p = index($0, "=")
            if (p == 0) next
            if (_grupo != "General") next
            if (apara(substr($0, 1, p - 1)) != CHAVE) next
            v = substr($0, p + 1)
            sub(/^[[:space:]]+/, "", v)
            _achou = 1
            _valor = v
            _local = (_dentro ? "dentro" : "fora")
        }
        END { if (_achou) printf "%s\t%s\n", _local, _valor }
    '
    return 0
}

#: Último valor ATIVO de uma chave em `[General]`. Vazio se não estiver ativa.
#:
#: VALOR VAZIO NÃO É CHAVE AUSENTE (achado de 06/08/2026, MEDIDO contra o
#: oráculo): `JustWorksRepairing=` faz o GKeyFile responder que a chave EXISTE,
#: com valor `''`. O dono devolvia string vazia, o `verificar` imprimia
#: `${jw:-ausente}` e dizia `ausente` — e `ausente` tem tratamento próprio no
#: doctor ("o BlueZ cai no default da distro"), que é uma afirmação diferente e
#: falsa. Aqui o valor vazio sai como `(vazio)`: existe, não é o nosso, e o
#: veredito o trata como qualquer outro valor inseguro.
_valor_ativo() {
    local bruto valor
    bruto="$(_ler_chave "$1" "$2")"
    [[ -n "${bruto}" ]] || return 0
    valor="${bruto#*$'\t'}"
    printf '%s\n' "${valor:-(vazio)}"
    return 0
}

#: A primeira linha que faz o GKeyFile RECUSAR O ARQUIVO INTEIRO, se houver.
#: Imprime `NUMERO<TAB>MOTIVO<TAB>TEXTO`, ou nada.
#:
#: ACHADO DE 06/08/2026, MEDIDO contra o oráculo: o GKeyFile não ignora linha
#: malformada — ele ABORTA A CARGA, e o `bluetoothd` fica sem config nenhuma.
#: Uma única linha solta em qualquer ponto do arquivo:
#:
#:     ERRO-DE-CARGA g-key-file-error-quark: Key file contains line
#:     "linha-solta-sem-igual" which is not a key-value pair, group, or comment
#:
#: e o mesmo vale para chave antes do primeiro `[grupo]` ("Key file does not
#: start with a group"). O dono único lia `JustWorksRepairing=confirm` normal e
#: respondia `veredito: OK` — a direção do engano é conservadora (ninguém fica
#: com `always` valendo), mas o veredito é FALSO nos dois sentidos que importam:
#: ela lê "está tudo certo" quando o BlueZ está sem NENHUMA das nossas chaves, e
#: o `aplicar` anuncia garantia que não existe.
#:
#: Isto é uma RÉPLICA das duas regras do GKeyFile, não o GKeyFile. Não há CLI do
#: GLib para chamar aqui, e um `python3 -c` no meio de um script de shell que o
#: install roda como root é dependência que não se paga. A bancada fecha a
#: diferença do jeito certo: cada caso é conferido contra o oráculo de verdade.
#:
#: NOTA DATADA — 07/08/2026: A RÉPLICA RECUSA MENOS QUE O ORÁCULO. GRAU: MEDIDO,
#: por execução, contra o GKeyFile de verdade (GLib 2.80.0). QUATRO formas fazem
#: o `bluetoothd` DESCARTAR O ARQUIVO INTEIRO enquanto esta função não devolve
#: nada e o `verificar` responde `veredito: OK` com saída 0:
#:
#:     =valor          nome de chave vazio    -> "is not a key-value pair"
#:     =               só o igual             -> "is not a key-value pair"
#:     cha[ve=valor    colchete no nome       -> "Invalid key name"
#:     cha]ve=valor    colchete no nome       -> "Invalid key name"
#:
#: E mais DUAS que não dão `OK`, mas mentem o motivo: grupo `[]` e grupo com
#: colchete no nome saem como `veredito: INSEGURO / JustWorksRepairing ausente`,
#: quando o que há é o arquivo descartado inteiro — a receita que a pessoa
#: seguir a partir daí conserta a coisa errada.
#:
#: NÃO curado: a cura é acrescentar as regras aqui E na `_TABELA_DA_RECUSA` de
#: `tests/unit/test_bluez_config_sh.py`, que hoje só tem casos que já caem nas
#: duas regras acima. A tabela medida, com a mensagem exata do GKeyFile em cada
#: linha, está na sprint SELO-VERDE-CEDO-DEMAIS-01, seção "ABERTO, GRAVIDADE
#: ALTA". Cuidado ao alargar: o GKeyFile é MAIS PERMISSIVO em pelo menos um
#: ponto (aceita valor com byte UTF-8 inválido), e réplica que recusasse ali
#: passaria a reprovar arquivo bom.
_linha_que_o_parser_recusa() {
    local arquivo="$1"
    [[ -f "${arquivo}" ]] || return 0
    _cat_conf "${arquivo}" | awk '
        function apara(s) {
            sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s
        }
        { sub(/\r$/, "") }
        {
            t = apara($0)
            if (t == "") next
            if (substr(t, 1, 1) == "#") next
            if (t ~ /^\[.*\]$/) { _grupo_visto = 1; next }
            if (index($0, "=") == 0) {
                printf "%d\tnao e par chave=valor, grupo nem comentario\t%s\n", NR, t
                exit
            }
            if (!_grupo_visto) {
                printf "%d\tchave antes de qualquer [grupo]\t%s\n", NR, t
                exit
            }
        }
    '
    return 0
}

#: `dentro`/`fora` do bloco hefesto para a linha que VENCE. Vazio se ausente.
#: É o que separa a promessa verdadeira da falsa no rebaixamento do `never`.
_local_ativo() {
    local bruto
    bruto="$(_ler_chave "$1" "$2")"
    [[ -n "${bruto}" ]] || return 0
    printf '%s\n' "${bruto%%$'\t'*}"
    return 0
}

_tem_bloco_nosso() {
    [[ -f "${MAIN_CONF}" ]] || return 1
    _cat_conf "${MAIN_CONF}" | grep -qE "${_RE_ABRE}"
}

#: Linhas que NÃO são nossas dentro do nosso bloco de sentinelas.
#:
#: O `_despir_main_conf` descarta a faixa inteira. Se alguém escreveu ali dentro
#: (é o lugar mais óbvio do arquivo para quem quer mexer em Bluetooth), a linha
#: some sem uma palavra — e chaves de fone/headset como `ControllerMode` e
#: `MultiProfile` são exatamente o que uma pessoa põe num main.conf. Nossas são:
#: comentário, linha em branco, cabeçalho de grupo e as DUAS chaves do bloco.
_alheio_no_bloco() {
    local origem="${1:-${MAIN_CONF}}"
    [[ -f "${origem}" ]] || return 0
    _cat_conf "${origem}" | awk -v ABRE="${_RE_ABRE}" -v FECHA="${_RE_FECHA}" '
        $0 ~ ABRE { _dentro = 1; next }
        _dentro && $0 ~ FECHA { _dentro = 0; next }
        !_dentro { next }
        /^[[:space:]]*(#|$)/ { next }
        /^[[:space:]]*\[[^]]*\][[:space:]]*$/ { next }
        /^[[:space:]]*(FastConnectable|JustWorksRepairing)[[:space:]]*=/ { next }
        { print }
    '
    return 0
}

#: Avisa, NOMEANDO, o que vai ser descartado junto com o bloco.
_avisar_alheio_no_bloco() {
    local linha visto=0
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        if [[ "${visto}" -eq 0 ]]; then
            _diz "ATENÇÃO: há linha que NÃO é nossa dentro do bloco hefesto — o bloco inteiro é reescrito, então ela SAI (o backup abaixo guarda o original):"
            visto=1
        fi
        _diz "  sai do arquivo: ${linha}"
    done < <(_alheio_no_bloco)
    if [[ "${visto}" -eq 1 ]]; then
        _diz "  se alguma dessas linhas era sua, ponha-a FORA das sentinelas do hefesto e ela sobrevive a toda execução"
    fi
}

# ---------------------------------------------------------------------------
# Reescrita do main.conf
# ---------------------------------------------------------------------------

# Monta em $1 (arquivo temporário) o main.conf SEM nada nosso:
#   (a) descarta as faixas das TRÊS sentinelas;
#   (b) neutraliza (comenta com a MARCA) chave nossa ativa fora de bloco;
#   (c) descarta as linhas em branco do FIM (preserva as internas).
#
# BUG-INSTALL-MAIN-CONF-CRESCE-01 (25/07): o (c) é o que torna o passo
# realmente idempotente. As sentinelas delimitam só o bloco; a linha em branco
# separadora que apensamos ficava FORA delas e sobrevivia — cada install
# empurrava o bloco uma linha para baixo (medido: +1 linha por execução, de 27
# a 34 linhas em oito execuções).
#
# Sai com 3 se uma sentinela de ABERTURA ficou sem fechamento. Isso é recusa
# deliberada: um `sed '/A/,/B/d'` com B ausente apaga até o FIM DO ARQUIVO, e
# era exatamente essa a forma do removedor antigo do uninstall. Preferimos não
# mexer a comer o resto do arquivo de alguém.
#
# A EXCEÇÃO DECLARADA da invariante "o `remover` devolve o arquivo byte a byte":
# por causa do (c), linhas em branco do FIM do arquivo ORIGINAL não voltam. Um
# main.conf que terminava em duas linhas vazias volta terminando na última linha
# com conteúdo. É o preço da idempotência (sem o (c), cada `aplicar` empurrava o
# bloco uma linha para baixo — medido: 27 a 34 linhas em oito execuções), e está
# fixado por teste (`test_remover_declara_a_excecao_das_linhas_em_branco_do_fim`)
# para que ninguém descubra isso por acidente.
_despir_main_conf() {
    local destino="$1" origem="${2:-${MAIN_CONF}}"
    _r awk -v MARCA="${MARCA}" -v ABRE="${_RE_ABRE}" -v FECHA="${_RE_FECHA}" '
        $0 ~ ABRE { _skip=1; next }
        _skip && $0 ~ FECHA { _skip=0; next }
        _skip { next }
        index($0, MARCA) == 1 { for (; _b > 0; _b--) print ""; print; next }
        /^[[:space:]]*(FastConnectable|JustWorksRepairing)[[:space:]]*=/ {
            for (; _b > 0; _b--) print ""
            print MARCA $0
            next
        }
        /^[[:space:]]*$/ { _b++; next }
        { for (; _b > 0; _b--) print ""; print }
        END { if (_skip) exit 3 }
    ' "${origem}" > "${destino}"
}

# Grava $1 em ${MAIN_CONF} se — e só se — o conteúdo for diferente.
# BUG-INSTALL-MAIN-CONF-BACKUP-INFINITO-01 (25/07): o backup era feito ANTES de
# saber se havia mudança, com timestamp no nome, e cada execução deixava mais
# um arquivo em /etc/bluetooth. Comparar primeiro é o que faz o no-op ser
# honesto. Devolve 0 (gravou ou já estava igual) ou 1 (falhou).
#
# A ESCRITA É ATÔMICA, e isso não é preciosismo (06/08/2026):
# a versão anterior fazia `install -m644 tmp /etc/bluetooth/main.conf`, que
# escreve NO LUGAR (mesmo inode, O_TRUNC). Disco cheio ou um kill no meio
# deixavam o main.conf DELA truncado — e como o nosso bloco fica no FIM, o corte
# cai DENTRO dele: sobra sentinela de abertura sem fechamento, e a partir daí
# `aplicar` E `remover` RECUSAM para sempre (é a recusa correta, e é um beco sem
# saída, com o doctor mandando rodar exatamente o que não pode funcionar). Agora
# o conteúdo novo nasce num temporário do MESMO diretório e entra por `mv` —
# rename é atômico no mesmo sistema de arquivos: ou o arquivo antigo inteiro, ou
# o novo inteiro, nunca um pedaço dos dois.
#
# O QUE ISTO NÃO COBRE (correção de 06/08/2026 — a frase anterior dizia "queda
# de energia" e era falsa): `rename(2)` dá ATOMICIDADE, não DURABILIDADE. Sem
# `fsync` no temporário e no diretório, uma queda de energia logo depois do `mv`
# pode deixar no disco o arquivo ANTIGO — nunca uma mistura dos dois, que é o
# estrago que importava aqui, mas também nunca com garantia de que o novo
# sobreviveu. Não pomos `fsync` de propósito: a mudança só vale no próximo start
# do bluetoothd (boot), e um boot depois de queda de energia re-executaria o
# install de qualquer forma. O que se promete é o que se entrega.
#
# LINK SIMBÓLICO (SUSPEITA COM MECANISMO, 06/08/2026): se `main.conf` for um
# symlink, o `mv -f` o SUBSTITUI por arquivo comum, e o alvo do link fica para
# trás intocado. NÃO é regressão — o `install -m644` da versão anterior seguia o
# link e reescrevia o alvo, o que é outro estrago, não menor — e não se aplica à
# máquina dela (MEDIDO: `/etc/bluetooth/main.conf` é arquivo comum). Fica dito
# aqui para quem encontrar o caso não achar que foi acidente.
#: Saída de `_copia_de_seguranca`. Variável global, e NÃO `$( )`, de propósito:
#: dentro de uma substituição de comando o `_lixo_add` roda num SUBSHELL e a
#: lista de lixo do processo pai não fica sabendo do arquivo em trânsito — o
#: `trap` de INT/TERM perderia exatamente o backup pela metade que ele existe
#: para limpar.
_BACKUP_FEITO=""

#: Guarda uma cópia fiel de `$1` ao lado dele, com o rótulo `$2`. O caminho sai
#: em `_BACKUP_FEITO`. Devolve 1 (e não deixa pedaço no disco) se a cópia não
#: puder ser conferida byte a byte.
#
# O NOME DO BACKUP NÃO PODE COLIDIR — achado de 06/08/2026, MEDIDO.
# Era `main.conf.bak.hefesto-${rotulo}$(date +%s)`: resolução de UM SEGUNDO,
# com um `cp` sem `-n`, sem teste de `-e` e sem `mktemp`. Duas gravações do
# MESMO rótulo dentro do mesmo segundo faziam a segunda SOBRESCREVER o
# backup da primeira — e isso acontece DENTRO do `aplicar`/`remover`, sem
# gesto dela, no par `remover; aplicar` que o próprio doctor sugere.
# Reproduzido: `aplicar` sobre o estado A, edição, `aplicar` de novo no
# mesmo segundo, e o backup do estado A não existe mais. O destruído é
# sempre o de MAIOR valor (o estado imediatamente anterior), o
# `_resumo_backups` não vê nada (um arquivo morre, outro nasce, a CONTAGEM
# não muda) e a mesma execução imprime "nenhum é apagado automaticamente",
# que passava a ser mentira.
# `mktemp` resolve pelo mecanismo e não pela sorte: O_EXCL, nome vindo do
# kernel, e os X no FIM porque é onde o mktemp os aceita.
#
# BACKUP PARCIAL NÃO É BACKUP — achado de 06/08/2026, MEDIDO: um `cp` que
# morre no meio deixava 118 bytes cortados dentro do bloco, sem limpeza e
# sem uma palavra; o `verificar` os contava como legítimos e o `podar` nunca
# os removia. A assimetria estava no corpo do `_gravar_se_mudou`: o caminho
# do temporário tinha `rm -f`, o do backup não.
# Aqui o backup só existe se o `cp` sair 0 E o `cmp` confirmar byte a byte.
# O que não passar é APAGADO e DITO, e o original não é tocado.
_copia_de_seguranca() {
    local origem="$1" rotulo="$2" backup
    _BACKUP_FEITO=""
    if ! backup="$(_r mktemp "${origem}.bak.hefesto-${rotulo}$(date +%s)-XXXXXX" 2>/dev/null)"; then
        _erro "não consegui criar o arquivo de backup ao lado de ${origem} — NÃO mexi nele"
        return 1
    fi
    _lixo_add "${backup}"
    if ! _r cp "${origem}" "${backup}" 2>/dev/null \
       || ! _r cmp -s "${origem}" "${backup}"; then
        _r rm -f "${backup}" 2>/dev/null || true
        _lixo_tirar "${backup}"
        _erro "o backup ${backup} saiu INCOMPLETO — apaguei o pedaço (backup pela metade tem cara de legítimo) e NÃO mexi em ${origem}"
        return 1
    fi
    # O backup nasce do mktemp com modo 600. Um backup do conffile dela tem de
    # ter o modo DELE, nem mais aberto nem mais fechado.
    _r chmod --reference="${origem}" "${backup}" 2>/dev/null || true
    _lixo_tirar "${backup}"
    _BACKUP_FEITO="${backup}"
    return 0
}

_gravar_se_mudou() {
    local candidato="$1" rotulo="$2" backup novo
    if _r cmp -s "${candidato}" "${MAIN_CONF}"; then
        _diz "main.conf já está como queremos, byte a byte — nada a reescrever (sem backup novo)"
        return 0
    fi
    _copia_de_seguranca "${MAIN_CONF}" "${rotulo}" || return 1
    backup="${_BACKUP_FEITO}"
    # Temporário no MESMO diretório: `mv` entre sistemas de arquivos diferentes
    # copia e volta a ser não-atômico. O ponto no início mantém o arquivo fora
    # de qualquer glob de config e do nosso próprio `main.conf.bak.hefesto-*`.
    if ! novo="$(_r mktemp "${ETC}/.main.conf.hefesto-novo.XXXXXX" 2>/dev/null)"; then
        _erro "não consegui criar temporário em ${ETC} — NÃO mexi em ${MAIN_CONF}"
        return 1
    fi
    _lixo_add "${novo}"
    # Dono, modo e rótulo do original: o `main.conf` é conffile do dpkg e não
    # pode voltar com permissão de temporário. Falha de `--reference` (coreutils
    # sem GNU) cai no 644, que é o modo do pacote.
    if _r cp "${candidato}" "${novo}" 2>/dev/null \
       && { _r chmod --reference="${MAIN_CONF}" "${novo}" 2>/dev/null \
            || _r chmod 644 "${novo}" 2>/dev/null; } \
       && { _r chown --reference="${MAIN_CONF}" "${novo}" 2>/dev/null || true; } \
       && { ! command -v chcon >/dev/null 2>&1 \
            || _r chcon --reference="${MAIN_CONF}" "${novo}" 2>/dev/null || true; } \
       && _r mv -f "${novo}" "${MAIN_CONF}" 2>/dev/null; then
        _lixo_tirar "${novo}"
        _diz "main.conf reescrito por troca atômica (backup: ${backup})"
        return 0
    fi
    _r rm -f "${novo}" 2>/dev/null || true
    _lixo_tirar "${novo}"
    _erro "não consegui reescrever ${MAIN_CONF} — o arquivo ficou INTACTO (backup em ${backup})"
    return 1
}

# ---------------------------------------------------------------------------
# Drop-ins de main.conf.d — as MESMAS invariantes do main.conf (invariante 2)
#
# Até 06/08/2026 este caminho era `install -Dm644 asset destino`, sem `cmp`, sem
# backup e sem uma palavra, e o `remover` era `rm -f`, também sem backup. Um
# arquivo editado à mão em `main.conf.d/hefesto-justworks.conf` era destruído SEM
# CÓPIA NENHUMA enquanto a mesma função imprimia "drop-ins de main.conf.d
# gravados" como sucesso.
#
# O CONTRA-ARGUMENTO, e por que não venceu: "o caminho é NOSSO, o nome é nosso,
# quem edita ali sabe o que faz". Só que o motivo da invariante não é a
# propriedade do caminho — é que aquilo é a config de rádio de alguém, e a
# própria sprint já tem a medição de quanto custa perder estado de config sem
# cópia. E o custo da simetria é um `cmp` no caminho feliz, que não gera arquivo
# nenhum. Onde a exceção continua valendo ela está DECLARADA no cabeçalho: igual
# byte a byte ao asset = nada a perder = sem backup.
#
# O backup fica AO LADO do drop-in e o nome não termina em `.conf`: um BlueZ que
# leia `main.conf.d/` lê `*.conf`, e um backup que virasse config seria trocar um
# defeito por outro. Pela mesma razão ele não entra no `main.conf.bak.hefesto-*`
# do `_lista_backups` (diretório diferente, prefixo diferente): a poda do
# `main.conf` não pode alcançá-lo por engano.
# ---------------------------------------------------------------------------

_gravar_dropin() {
    local asset="$1" destino="$2" nome
    nome="$(basename "${destino}")"
    if [[ -f "${destino}" ]] && _r cmp -s "${asset}" "${destino}" 2>/dev/null; then
        return 0
    fi
    if [[ -e "${destino}" ]]; then
        if ! _copia_de_seguranca "${destino}" "dropin-"; then
            _erro "NÃO reescrevi ${nome}: ele difere do nosso asset e não consegui guardar cópia antes"
            return 1
        fi
        _diz "ATENÇÃO: ${nome} já existia com conteúdo DIFERENTE do nosso e foi reescrito — a versão anterior está em ${_BACKUP_FEITO}"
    fi
    _r install -Dm644 "${asset}" "${destino}" 2>/dev/null
}

_remover_dropin() {
    local asset="$1" destino="$2" nome
    nome="$(basename "${destino}")"
    [[ -e "${destino}" ]] || return 0
    if ! _r cmp -s "${asset}" "${destino}" 2>/dev/null; then
        if ! _copia_de_seguranca "${destino}" "dropin-"; then
            _erro "NÃO removi ${nome}: ele difere do nosso asset e não consegui guardar cópia antes"
            return 1
        fi
        _diz "ATENÇÃO: ${nome} tinha conteúdo DIFERENTE do nosso — guardei em ${_BACKUP_FEITO} antes de remover"
    fi
    _r rm -f "${destino}" || return 1
    _diz "drop-in ${nome} removido"
    return 0
}

# ---------------------------------------------------------------------------
# Backups: contar e reportar é automático; APAGAR nunca é
# ---------------------------------------------------------------------------

# `%T@\t%p`, do mais NOVO para o mais VELHO. Nunca casa arquivo que não tenha o
# nosso prefixo `main.conf.bak.hefesto-` — o `main.conf.bak.` de outra
# ferramenta que existe na máquina dela não é nosso e fica onde está.
#
# ARQUIVO VAZIO NÃO É BACKUP (achado de 06/08/2026, MEDIDO). O `_copia_de_
# seguranca` cria o arquivo com `mktemp` (nasce com ZERO byte) e só depois o
# preenche com `cp`. Um SIGKILL entre os dois — e SIGKILL não tem `trap`, então
# a limpeza que cobre INT/TERM/HUP não roda — deixa no disco um
# `main.conf.bak.hefesto-...` de 0 byte. O `verificar` o contava dentro de
# `backups-hefesto:` como legítimo e o `_resumo_backups` o somava na frase do
# `aplicar`: ela lia "37 backups" quando tinha 36 e um cadáver. Backup vazio com
# cara de legítimo é o mesmo defeito do backup pela metade, um passo antes.
# Aqui ele deixa de contar como backup e passa a ser REPORTADO como suspeito —
# do mesmo jeito que os temporários órfãos, e pelo mesmo motivo: reportar é
# obrigação, apagar não fazemos.
_lista_backups() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
         ! -empty -printf '%T@\t%p\n' 2>/dev/null \
        | sort -rn -k1,1 -k2,2
    return 0
}

# Backups de ZERO byte: existem, têm o nosso nome, e não guardam nada.
_lista_backups_vazios() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
         -empty 2>/dev/null | sort
    return 0
}

# Temporários de troca atômica que ficaram para trás. Com o `trap` desta versão
# isso não deveria acontecer mais — mas um SIGKILL não tem trap, e o que já está
# no disco dela hoje ninguém varreu. Reportar é obrigação; APAGAR não fazemos,
# pela mesma regra dos backups: um temporário órfão pode ser a única cópia do
# conteúdo que a máquina tentou gravar quando morreu.
_lista_orfaos() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name '.main.conf.hefesto-novo.*' \
         2>/dev/null | sort
    return 0
}

# O que o `aplicar` e o `remover` fazem com backup antigo: CONTAM e DIZEM.
# Os vazios NÃO entram na conta (não guardam nada), e por isso mesmo são ditos
# à parte: sumir da frase sem uma palavra seria trocar um número errado por
# silêncio.
_resumo_backups() {
    local n bytes vazios n_vazios=0
    [[ -d "${ETC}" ]] || return 0
    vazios="$(_lista_backups_vazios)"
    [[ -z "${vazios}" ]] || n_vazios="$(printf '%s\n' "${vazios}" | wc -l)"
    n="$(_lista_backups | wc -l)"
    if [[ "${n_vazios}" -gt 0 ]]; then
        _diz "ATENÇÃO: ${n_vazios} arquivo(s) com nome de backup nosso e ZERO byte em ${ETC} — não guardam nada e NÃO contam como backup (marca de execução morta entre criar e copiar); listados por 'bash scripts/bluez_config.sh verificar'"
    fi
    [[ "${n}" -gt 0 ]] || return 0
    bytes="$(
        find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
             ! -empty -printf '%s\n' 2>/dev/null | awk '{ s += $1 } END { print s + 0 }'
    )"
    _diz "backups do hefesto em ${ETC}: ${n} arquivo(s), ${bytes} byte(s) — nenhum é apagado automaticamente"
    _diz "  para revisar/podar (simula por padrão): bash scripts/bluez_config.sh podar"
    return 0
}

# Poda EXPLÍCITA. Simula por padrão; `--aplicar` para valer. Duas proteções que
# não dependem de retenção nenhuma:
#   - o mais ANTIGO nunca sai: é o estado mais próximo do pré-hefesto;
#   - nenhum ESTADO some do disco: cada conteúdo distinto guarda pelo menos uma
#     cópia, e a que fica é a mais ANTIGA daquele conteúdo (entre bytes iguais,
#     a de mtime menor é a que diz quando aquele estado APARECEU).
#
# A PROTEÇÃO ERA POR ARQUIVO E A FRASE PROMETIA ESTADO (achado de 06/08/2026,
# MEDIDO — correção de decisão gravada). A regra anterior era "nenhum OUTRO
# backup tem os mesmos bytes": protegia só o conteúdo que aparecia UMA vez. Com
# um conteúdo repetido em N cópias e TODAS elas fora da retenção, as N saíam
# juntas e aquele estado do main.conf dela sumia do disco por completo — e a
# frase impressa no fim, "o mais antigo e os de conteúdo único ficam sempre",
# lia-se como promessa de ESTADO e não era. Reproduzido com 9 backups em 3
# estados de 3 cópias e retenção 1: o estado do meio perdia as três.
# O teste que existia não mordia esse cenário (usava 35 arquivos IDÊNTICOS, em
# que a regra velha e a nova dão o mesmo resultado); hoje morde
# `test_podar_nunca_faz_um_estado_sumir_do_disco`.
_podar() {
    local modo="${1:---dry-run}" de_verdade=0
    case "${modo}" in
        --dry-run|-n)           de_verdade=0 ;;
        --aplicar|--de-verdade) de_verdade=1 ;;
        *)
            _erro "uso: bluez_config.sh podar [--dry-run|--aplicar]"
            return 2
            ;;
    esac
    if ! [[ "${BACKUPS_MANTER}" =~ ^[0-9]+$ ]]; then
        _erro "retenção inválida em HEFESTO_BT_BACKUPS_MANTER: ${BACKUPS_MANTER}"
        return 2
    fi

    local -a caminhos=() somas=() alvos=()
    local linha p soma i total
    while IFS= read -r linha; do
        [[ -n "${linha}" ]] || continue
        caminhos+=("${linha#*$'\t'}")
    done < <(_lista_backups)

    total="${#caminhos[@]}"
    if [[ "${total}" -eq 0 ]]; then
        _diz "não há backup do hefesto em ${ETC} — nada a podar"
        return 0
    fi
    if [[ "${BACKUPS_MANTER}" -lt 1 ]]; then
        _diz "retenção declarada 0 = poda desligada; ${total} backup(s) preservado(s)"
        return 0
    fi

    for p in "${caminhos[@]}"; do
        soma="$(_r cksum "${p}" 2>/dev/null | awk '{ print $1 "-" $2 }')"
        # Ilegível vira soma ÚNICA (o próprio caminho): não sabemos o que há
        # dentro, então ninguém pode alegar que há cópia disso em outro lugar.
        [[ -n "${soma}" ]] || soma="ilegivel:${p}"
        somas+=("${soma}")
    done

    # PASSO 1 — que ESTADOS já estão garantidos por outra regra: os
    # `BACKUPS_MANTER` mais novos (a retenção) e o mais antigo.
    local -A estado_vivo=()
    for (( i = 0; i < total; i++ )); do
        if [[ "${i}" -lt "${BACKUPS_MANTER}" || "${i}" -eq $(( total - 1 )) ]]; then
            estado_vivo["${somas[i]}"]=1
        fi
    done

    # PASSO 2 — do MAIS ANTIGO para o mais novo: entre os candidatos, o primeiro
    # de cada estado ainda sem cópia garantida vira GUARDIÃO daquele estado. A
    # direção do laço é a decisão: entre cópias de bytes idênticos, a de mtime
    # menor é a que registra QUANDO aquele estado apareceu, e é essa que
    # interessa a quem for explicar o colapso "404 linhas -> 3 linhas".
    local -A guardiao=()
    for (( i = total - 1; i >= 0; i-- )); do
        [[ "${i}" -ge "${BACKUPS_MANTER}" ]] || continue
        [[ "${i}" -ne $(( total - 1 )) ]] || continue
        [[ -z "${estado_vivo["${somas[i]}"]:-}" ]] || continue
        estado_vivo["${somas[i]}"]=1
        guardiao["${i}"]=1
    done

    # PASSO 3 — sai só quem tem OUTRA cópia dos mesmos bytes sobrevivendo.
    for (( i = 0; i < total; i++ )); do
        p="${caminhos[i]}"
        [[ "${i}" -ge "${BACKUPS_MANTER}" ]] || continue
        if [[ "${i}" -eq $(( total - 1 )) ]]; then
            _diz "preservado (o MAIS ANTIGO nunca sai — é o estado mais próximo do pré-hefesto): ${p}"
            continue
        fi
        if [[ -n "${guardiao["${i}"]:-}" ]]; then
            _diz "preservado (ÚNICA cópia deste conteúdo que sobreviveria — nenhum estado do main.conf dela some do disco): ${p}"
            continue
        fi
        alvos+=("${p}")
    done

    if [[ "${#alvos[@]}" -eq 0 ]]; then
        _diz "poda: nada a remover (${total} backup(s); retenção ${BACKUPS_MANTER}; o resto está protegido)"
        return 0
    fi
    if [[ "${de_verdade}" -eq 0 ]]; then
        _diz "poda SIMULADA (--dry-run é o padrão): ${#alvos[@]} de ${total} backup(s) sairiam:"
        for p in "${alvos[@]}"; do
            _diz "  sairia: ${p}"
        done
        _diz "para remover DE VERDADE: bash scripts/bluez_config.sh podar --aplicar"
        return 0
    fi

    local removidos=0 falhos=0
    for p in "${alvos[@]}"; do
        # Anunciar remoção que não aconteceu é mentir sobre o disco dela: o
        # `|| true` do desenho anterior engolia a falha do `rm` e a frase saía
        # igual. Aqui cada arquivo é conferido DEPOIS.
        if _r rm -f "${p}" 2>/dev/null && [[ ! -e "${p}" ]]; then
            removidos=$(( removidos + 1 ))
            _diz "removido: ${p}"
        else
            falhos=$(( falhos + 1 ))
            _erro "não consegui remover ${p}"
        fi
    done
    _diz "poda: ${removidos} de ${total} backup(s) removido(s) (retenção ${BACKUPS_MANTER}; o mais antigo fica sempre, e cada conteúdo distinto guarda pelo menos uma cópia — nenhum estado do main.conf some do disco)"
    [[ "${falhos}" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# aplicar
# ---------------------------------------------------------------------------
_aplicar() {
    local rc=0 tmp anterior onde a sem_main_conf=0 conferido jw_final fc_final
    local recusa_final

    for a in "${BLOCO}" "${ASSET_FAST}" "${ASSET_JW}"; do
        if [[ ! -f "${a}" ]]; then
            _erro "asset ausente: ${a}"
            return 1
        fi
    done

    if [[ ! -d "${ETC}" ]]; then
        _diz "sem ${ETC} (BlueZ ausente?) — config do BlueZ pulada"
        return 0
    fi

    # O RECONHECIMENTO que faltava: dizer com todas as letras que havia um
    # valor inseguro no disco, e que ele estava DENTRO do nosso bloco. Sem
    # isto a correção acontecia em silêncio e ninguém sabia que a máquina
    # esteve exposta (foi assim que o `always` viveu quatro dias depois de a
    # sprint declarar a E1 "FEITA").
    if _conf_ilegivel; then
        _erro "não consigo LER ${MAIN_CONF} — sem leitura não sei o que estou reescrevendo, e não mexo"
        return 1
    fi

    anterior="$(_valor_ativo JustWorksRepairing "${MAIN_CONF}")"
    onde="$(_local_ativo JustWorksRepairing "${MAIN_CONF}")"
    if [[ -n "${anterior}" && "${anterior}" != "${VALOR_SEGURO}" ]]; then
        if [[ "${anterior}" == "never" ]]; then
            # ACHADO REGISTRADO (06/08/2026): `never` é MAIS restritivo que o
            # nosso `confirm` — recusa todo re-pareamento por Just Works de quem
            # já tem bond, sem perguntar a ninguém. Rebaixar em silêncio seria
            # tratar valor mais seguro como se fosse o `always`. Ainda assim
            # rebaixamos, e por um motivo declarado: com `never`, o controle
            # dela deixa de re-parear quando o bond se perde (o caso que a Onda
            # R veio resolver) e o sintoma aparece como "o controle não conecta
            # mais".
            #
            # A PROMESSA ERA FALSA NO LUGAR MAIS PROVÁVEL (achado de 06/08/2026,
            # MEDIDO): o aviso dizia, sempre, "a sua linha é neutralizada, não
            # apagada, e volta inteira". Isso é verdade FORA do bloco, onde a
            # linha vira `#hefesto-desativou# ...` e o `remover` a devolve. É
            # FALSO DENTRO do bloco — e dentro do bloco é exatamente onde vai
            # escrever quem leu o aviso do doctor e resolveu endurecer o valor,
            # porque é ali que a chave já está. Ali o `_despir_main_conf`
            # descarta a faixa inteira, nenhuma MARCA é gravada, o `remover`
            # entrega arquivo SEM a chave, e o `_avisar_alheio_no_bloco` cala
            # porque `JustWorksRepairing` está na lista de exceções (a linha é,
            # afinal, a que NÓS escrevemos ali).
            # A cura é a promessa deixar de ser feita onde não vale, e o aviso
            # NOMEAR o que vai sumir e onde a linha sobrevive.
            _diz "ATENÇÃO: JustWorksRepairing=never já estava ativo — é MAIS restritivo que o nosso ${VALOR_SEGURO}, e vamos REBAIXAR (RADIO-ABERTO-01)"
            _diz "  'never' recusa todo re-pareamento de quem já tem bond; '${VALOR_SEGURO}' aceita SÓ com confirmação do agente"
            if [[ "${onde}" == "dentro" ]]; then
                _diz "  esse 'never' está DENTRO do bloco hefesto, e o bloco inteiro é REESCRITO: a linha SAI agora e o 'remover' NÃO a devolve — só o backup abaixo guarda"
                _diz "  se 'never' foi escolha sua, escreva-a FORA das sentinelas do hefesto: ali ela é neutralizada, não apagada, e volta inteira no 'remover'"
            else
                _diz "  se 'never' foi escolha sua, rode 'bash scripts/bluez_config.sh remover': a sua linha está FORA do bloco, é neutralizada, não apagada, e volta inteira"
            fi
        elif _tem_bloco_nosso; then
            _diz "ATENÇÃO: JustWorksRepairing=${anterior} escrito por uma versão ANTERIOR do hefesto — corrigindo para ${VALOR_SEGURO} (RADIO-ABERTO-01)"
        else
            _diz "ATENÇÃO: JustWorksRepairing=${anterior} ativo fora do bloco hefesto — neutralizando e assumindo ${VALOR_SEGURO} (RADIO-ABERTO-01)"
        fi
    fi

    # main.conf primeiro: é o caminho que o bluetoothd desta casa lê de fato.
    if [[ -f "${MAIN_CONF}" ]]; then
        _avisar_alheio_no_bloco
        tmp="$(mktemp)"
        _lixo_add "${tmp}"
        if _despir_main_conf "${tmp}"; then
            { printf '\n'; cat "${BLOCO}"; } >> "${tmp}"
            _gravar_se_mudou "${tmp}" "" || rc=1
        else
            _erro "sentinela de abertura sem fechamento em ${MAIN_CONF} — não mexi no arquivo (conserte a mão e rode de novo)"
            rc=1
        fi
        rm -f "${tmp}"
        _lixo_tirar "${tmp}"
    else
        _diz "sem ${MAIN_CONF} (BlueZ ausente?) — bloco não apensado"
        sem_main_conf=1
    fi

    # Drop-ins POR CIMA, nunca no lugar: quando o diretório existe os dois
    # lugares passam a declarar o mesmo valor, e o instalador deixa de poder
    # anunciar `confirm` enquanto o `always` vive no main.conf.
    if [[ -d "${DROPIN_DIR}" ]]; then
        if _gravar_dropin "${ASSET_FAST}" "${DROPIN_FAST}" \
           && _gravar_dropin "${ASSET_JW}" "${DROPIN_JW}"; then
            _diz "drop-ins de main.conf.d gravados (mesmo valor do bloco: FastConnectable=true, JustWorksRepairing=${VALOR_SEGURO})"
        else
            _erro "drop-in de config do BlueZ falhou em ${DROPIN_DIR}"
            rc=1
        fi
    fi

    # A CONFERÊNCIA FINAL: releia o DISCO antes de prometer qualquer coisa.
    #
    # ACHADO DE 06/08/2026 (MEDIDO): com `assets/bluetooth/hefesto-bt.block` de
    # ZERO BYTE — asset truncado no build, no rsync ou no empacotamento — o
    # `aplicar` saía com rc=0 anunciando "JustWorksRepairing=confirm +
    # FastConnectable=true garantidos" e o arquivo final não tinha a chave
    # nenhuma. Cada passo tinha dado certo; o resultado não existia. É a mesma
    # família do defeito que abriu esta sprint (o instalador anunciando
    # `confirm` com o `always` vivo no disco), e a cura estava a uma chamada de
    # distância: o `_verificar` já sabe ler o estado, e ler pelo MESMO caminho
    # do doctor é o que impede as duas bocas de divergirem de novo.
    if [[ "${rc}" -eq 0 && "${sem_main_conf}" -eq 0 ]]; then
        # A LINHA QUE O PARSER RECUSA vem ANTES, porque explica o resto: com ela
        # no arquivo, o `bluetoothd` descarta TUDO e a nossa chave não vale nada
        # mesmo estando escrita. Dizer só "a garantia não está lá" mandaria ela
        # conferir o asset, que está certo, em vez da linha, que não está.
        recusa_final="$(_linha_que_o_parser_recusa "${MAIN_CONF}")"
        if [[ -n "${recusa_final}" ]]; then
            _erro "${MAIN_CONF} tem na linha $(printf '%s' "${recusa_final}" | cut -f1) algo que o parser do bluetoothd (GKeyFile) RECUSA: '$(printf '%s' "${recusa_final}" | cut -f3)' ($(printf '%s' "${recusa_final}" | cut -f2))"
            _erro "  uma linha recusada invalida o ARQUIVO INTEIRO — o bluetoothd fica sem config nenhuma, e a nossa chave também não vale. Conserte essa linha à mão e rode de novo"
            rc=1
        fi
        conferido="$(_verificar 2>/dev/null || true)"
        jw_final="$(printf '%s\n' "${conferido}" | sed -n 's/^JustWorksRepairing: //p')"
        fc_final="$(printf '%s\n' "${conferido}" | sed -n 's/^FastConnectable: //p')"
        if [[ "${rc}" -eq 0 \
              && ( "${jw_final}" != "${VALOR_SEGURO}" || "${fc_final}" != "true" ) ]]; then
            _erro "reli ${MAIN_CONF} DEPOIS de gravar e a garantia não está lá (JustWorksRepairing=${jw_final:-ausente}, FastConnectable=${fc_final:-ausente}) — confira ${BLOCO}"
            rc=1
        fi
    fi

    _resumo_backups
    # A frase da garantia só sai quando a garantia EXISTE. Anunciar sucesso
    # depois de uma recusa foi exatamente o que deixou o `always` viver quatro
    # dias com o instalador dizendo que tinha instalado `confirm`. Vale também
    # para o caso "existe /etc/bluetooth mas não existe main.conf": ali não
    # escrevemos NADA no arquivo que o bluetoothd lê, e dizer "garantidos"
    # seria a mesma mentira em outra roupa.
    if [[ "${rc}" -eq 0 && "${sem_main_conf}" -eq 1 ]]; then
        _diz "NADA garantido: ${MAIN_CONF} não existe (BlueZ ausente?) — nenhuma chave foi escrita nele"
    elif [[ "${rc}" -eq 0 ]]; then
        _diz "JustWorksRepairing=${VALOR_SEGURO} + FastConnectable=true garantidos — VALEM NO PRÓXIMO BOOT (ou restart natural do bluetoothd)"
        _diz "NÃO reiniciamos o bluetoothd de propósito: isso derrubaria os controles BT conectados agora"
    else
        _erro "config do BlueZ NÃO ficou garantida — confira as mensagens acima antes de confiar no rádio"
    fi
    return "${rc}"
}

# ---------------------------------------------------------------------------
# remover
# ---------------------------------------------------------------------------
_remover() {
    local rc=0 tmp devolvido depois

    if _conf_ilegivel; then
        _erro "não consigo LER ${MAIN_CONF} — sem leitura não sei se há bloco nosso, e concluir que não há seria deixar o bloco no disco"
        return 1
    fi

    _remover_dropin "${ASSET_FAST}" "${DROPIN_FAST}" || rc=1
    _remover_dropin "${ASSET_JW}" "${DROPIN_JW}" || rc=1

    # UM backup por execução, não um por bloco. Os três removedores antigos
    # faziam `cp` cada um por conta própria e sem `cmp`: numa máquina com os
    # dois blocos legados MAIS o unificado, uma única desinstalação deixava
    # TRÊS arquivos novos em /etc/bluetooth.
    if [[ -f "${MAIN_CONF}" ]]; then
        if _tem_bloco_nosso || _cat_conf "${MAIN_CONF}" | grep -qF "${MARCA}"; then
            _avisar_alheio_no_bloco
            tmp="$(mktemp)"
            _lixo_add "${tmp}"
            if _despir_main_conf "${tmp}"; then
                # Diferente do `aplicar`, aqui NÃO reapensamos o bloco: o que
                # sobra é o arquivo sem nada nosso, com as chaves de terceiro
                # que tínhamos neutralizado DEVOLVIDAS ao estado ativo.
                #
                # O temporário SAI de mktemp (O_EXCL) e não de um sufixo fixo:
                # `> "${tmp}.devolvido"` era nome previsível, sem exclusão, e o
                # mesmo descuido de escrita não-atômica que custou o achado do
                # main.conf truncado.
                devolvido="$(mktemp)"
                _lixo_add "${devolvido}"
                _r awk -v MARCA="${MARCA}" '
                    index($0, MARCA) == 1 { print substr($0, length(MARCA) + 1); next }
                    { print }
                ' "${tmp}" > "${devolvido}"
                mv -f "${devolvido}" "${tmp}"
                _lixo_tirar "${devolvido}"

                # O AVISO SIMÉTRICO. O `aplicar` grita quando encontra
                # JustWorksRepairing perigoso; a operação INVERSA era muda sobre
                # o valor que esta mesma sprint classifica como injeção de
                # teclas. Correção silenciosa foi o que deixou o `always` viver
                # quatro dias — devolução silenciosa é o mesmo defeito de costas.
                depois="$(_valor_ativo JustWorksRepairing "${tmp}")"
                if [[ -n "${depois}" && "${depois}" != "${VALOR_SEGURO}" ]]; then
                    if [[ "${depois}" == "always" ]]; then
                        _diz "ATENÇÃO: ao remover o bloco, JustWorksRepairing=always volta a ficar ATIVO no main.conf — era a linha que já estava aí, e nós só a tínhamos neutralizado"
                        _diz "  'always' remove a última recusa do BlueZ ao re-pareamento por Just Works de quem já tem bond: com agente NoInputNoOutput isso termina em INJEÇÃO DE TECLAS (RADIO-ABERTO-01)"
                        _diz "  se essa linha não é sua, apague-a à mão de ${MAIN_CONF} — nós não apagamos config de terceiro"
                    else
                        _diz "ATENÇÃO: ao remover o bloco, JustWorksRepairing=${depois} volta a ficar ATIVO no main.conf (linha sua, que tínhamos apenas neutralizado) — esta casa instala '${VALOR_SEGURO}'"
                    fi
                elif [[ -z "${depois}" ]]; then
                    _diz "sem o nosso bloco, JustWorksRepairing deixa de estar declarado — o BlueZ cai no default da distro, que não é decisão desta casa"
                fi

                _gravar_se_mudou "${tmp}" "uninstall-" || rc=1
                _diz "(vale no próximo boot/restart do bluetoothd — não reiniciamos o serviço)"
            else
                _erro "sentinela de abertura sem fechamento em ${MAIN_CONF} — não mexi no arquivo (remova o bloco à mão)"
                rc=1
            fi
            rm -f "${tmp}"
            _lixo_tirar "${tmp}"
        fi
    fi

    _resumo_backups
    return "${rc}"
}

# ---------------------------------------------------------------------------
# verificar — só leitura, e é o que o doctor.sh consome DE VERDADE
#
# (Até 06/08/2026 este comentário afirmava que o doctor consumia e não era
# verdade: o `check_bluez_justworks_repairing` reimplementava o mesmo `sed`
# inline. Duas fontes para a mesma regra é a classe de defeito que esta leva
# veio fechar. Hoje o doctor chama `verificar` e lê estas linhas.)
# ---------------------------------------------------------------------------
_verificar() {
    local jw fc n_backups=0 bytes_backups=0 veredito=0 orfaos orfao n_orfaos=0
    local dropin dropin_jw vazios vazio n_vazios=0 recusa

    if _conf_ilegivel; then
        printf 'main.conf: ilegível\n'
        printf 'JustWorksRepairing: ilegível\n'
        printf 'FastConnectable: ilegível\n'
        printf 'veredito: DESCONHECIDO (sem permissão de leitura em %s)\n' "${MAIN_CONF}"
        return 1
    fi

    # UMA linha malformada invalida o ARQUIVO INTEIRO para o bluetoothd. Ler as
    # chaves e responder OK sobre um arquivo que o parser real descarta é o
    # falso veredito mais silencioso que existe — nenhuma chave nossa vale, e
    # nada na tela dizia isso.
    recusa="$(_linha_que_o_parser_recusa "${MAIN_CONF}")"
    if [[ -n "${recusa}" ]]; then
        printf 'main.conf: recusado pelo parser (linha %s: %s — %s)\n' \
            "$(printf '%s' "${recusa}" | cut -f1)" \
            "$(printf '%s' "${recusa}" | cut -f3)" \
            "$(printf '%s' "${recusa}" | cut -f2)"
        printf 'JustWorksRepairing: recusado\n'
        printf 'FastConnectable: recusado\n'
        printf 'veredito: RECUSADO (o bluetoothd descarta %s inteiro; nenhuma chave vale)\n' \
            "${MAIN_CONF}"
        return 1
    fi

    printf 'main.conf: %s\n'   "$([[ -f "${MAIN_CONF}" ]] && echo presente || echo ausente)"
    printf 'main.conf.d: %s\n' "$([[ -d "${DROPIN_DIR}" ]] && echo presente || echo ausente)"
    printf 'bloco-hefesto: %s\n' "$(_tem_bloco_nosso && echo presente || echo ausente)"
    printf 'dropin-justworks: %s\n' "$([[ -f "${DROPIN_JW}" ]] && echo presente || echo ausente)"
    printf 'dropin-fastconnectable: %s\n' "$([[ -f "${DROPIN_FAST}" ]] && echo presente || echo ausente)"

    jw="$(_valor_ativo JustWorksRepairing "${MAIN_CONF}")"
    fc="$(_valor_ativo FastConnectable "${MAIN_CONF}")"
    printf 'JustWorksRepairing: %s\n' "${jw:-ausente}"
    printf 'FastConnectable: %s\n' "${fc:-ausente}"

    # OS DROP-INS TAMBÉM SÃO LIDOS AQUI — e por que só REPORTAMOS (06/08/2026).
    #
    # Levantado na verificação adversarial como SUSPEITA COM MECANISMO: o
    # `aplicar` grava drop-ins POR CIMA quando `main.conf.d` existe, mas o
    # `verificar` nunca lia VALOR de lá; um drop-in de terceiro que ordene
    # DEPOIS do nosso venceria e o veredito continuaria `OK`.
    #
    # MEDIDO nesta máquina, em 06/08/2026, três vezes pelo mesmo lado:
    #   - `strings /usr/libexec/bluetooth/bluetoothd` (bluez 5.86 do backport)
    #     tem `%*s/main.conf` e ZERO ocorrências de `main.conf.d`;
    #   - `/etc/bluetooth/main.conf.d` NÃO EXISTE;
    #   - `dpkg -L bluez` não lista o diretório.
    # Ou seja: aqui o mecanismo do drop-in não está ligado, e fazer o VEREDITO
    # depender de um arquivo que este bluetoothd não lê seria alarme falso — o
    # defeito de costas para o que esta sprint veio curar. Então o veredito
    # continua saindo do `main.conf`, que é o que vale nesta casa, e os drop-ins
    # entram como LINHA DE RELATÓRIO: quem rodar num BlueZ que os leia vê o
    # conflito com todas as letras, em vez de não ver nada.
    if [[ -d "${DROPIN_DIR}" ]]; then
        while IFS= read -r dropin; do
            [[ -n "${dropin}" ]] || continue
            dropin_jw="$(_valor_ativo JustWorksRepairing "${dropin}")"
            [[ -n "${dropin_jw}" ]] || continue
            printf 'dropin-JustWorksRepairing: %s=%s\n' \
                "$(basename "${dropin}")" "${dropin_jw}"
            if [[ "${dropin_jw}" != "${VALOR_SEGURO}" ]]; then
                printf 'dropin-em-conflito: %s declara %s (esperado %s)\n' \
                    "$(basename "${dropin}")" "${dropin_jw}" "${VALOR_SEGURO}"
            fi
        done < <(find "${DROPIN_DIR}" -maxdepth 1 -type f -name '*.conf' \
                      2>/dev/null | sort)
    fi

    if [[ -d "${ETC}" ]]; then
        n_backups="$(_lista_backups | wc -l)"
        bytes_backups="$(
            find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
                 ! -empty -printf '%s\n' 2>/dev/null | awk '{ s += $1 } END { print s + 0 }'
        )"
    fi
    printf 'backups-hefesto: %s\n' "${n_backups}"
    printf 'backups-hefesto-bytes: %s\n' "${bytes_backups}"

    # Os de ZERO byte, nomeados um a um — a mesma dignidade que os temporários
    # órfãos já tinham. Contá-los como backup era dizer a ela que há cópia do
    # estado do main.conf onde não há nada.
    vazios="$(_lista_backups_vazios)"
    n_vazios=0
    [[ -z "${vazios}" ]] || n_vazios="$(printf '%s\n' "${vazios}" | wc -l)"
    printf 'backups-suspeitos: %s\n' "${n_vazios}"
    if [[ "${n_vazios}" -gt 0 ]]; then
        while IFS= read -r vazio; do
            [[ -n "${vazio}" ]] || continue
            printf 'backup-suspeito: %s (ZERO byte — não guarda nada)\n' "${vazio}"
        done <<<"${vazios}"
    fi

    orfaos="$(_lista_orfaos)"
    n_orfaos=0
    [[ -z "${orfaos}" ]] || n_orfaos="$(printf '%s\n' "${orfaos}" | wc -l)"
    printf 'temporarios-orfaos: %s\n' "${n_orfaos}"
    if [[ "${n_orfaos}" -gt 0 ]]; then
        while IFS= read -r orfao; do
            [[ -n "${orfao}" ]] || continue
            printf 'temporario-orfao: %s\n' "${orfao}"
        done <<<"${orfaos}"
    fi

    if [[ ! -f "${MAIN_CONF}" ]]; then
        printf 'veredito: SEM-BLUEZ\n'
        return 0
    fi
    if [[ "${jw}" != "${VALOR_SEGURO}" ]]; then
        printf 'veredito: INSEGURO (JustWorksRepairing=%s; esperado %s)\n' \
            "${jw:-ausente}" "${VALOR_SEGURO}"
        veredito=1
    else
        printf 'veredito: OK\n'
    fi
    return "${veredito}"
}

case "${1:-}" in
    aplicar)   _aplicar ;;
    remover)   _remover ;;
    verificar) _verificar ;;
    podar)     _podar "${2:---dry-run}" ;;
    *)
        _erro "uso: bluez_config.sh {aplicar|remover|verificar|podar [--dry-run|--aplicar]}"
        exit 2
        ;;
esac
