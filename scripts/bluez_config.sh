#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ETC="${HEFESTO_BT_ETC:-/etc/bluetooth}"
ASSETS="${HEFESTO_BT_ASSETS:-${_SCRIPT_DIR}/../assets/bluetooth}"
SUDO="${HEFESTO_BT_SUDO-sudo}"
BACKUPS_MANTER="${HEFESTO_BT_BACKUPS_MANTER:-10}"

MAIN_CONF="${ETC}/main.conf"
DROPIN_DIR="${ETC}/main.conf.d"
DROPIN_FAST="${DROPIN_DIR}/hefesto-fastconnectable.conf"
DROPIN_JW="${DROPIN_DIR}/hefesto-justworks.conf"

BLOCO="${ASSETS}/hefesto-bt.block"
ASSET_FAST="${ASSETS}/hefesto-fastconnectable.conf"
ASSET_JW="${ASSETS}/hefesto-justworks.conf"

MARCA='#hefesto-desativou# '

VALOR_SEGURO='confirm'

_RE_ABRE='^# >>> hefesto (bluetooth|FastConnectable|JustWorksRepairing) >>>'
_RE_FECHA='^# <<< hefesto (bluetooth|FastConnectable|JustWorksRepairing) <<<'

_diz()  { printf '      %s\n' "$*"; }
_erro() { printf 'bluez_config.sh: %s\n' "$*" >&2; }

_r() {
    if [[ -n "${SUDO}" ]]; then
        "${SUDO}" "$@"
    else
        "$@"
    fi
}

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

_cat_conf() {
    local arquivo="$1"
    if [[ -r "${arquivo}" ]]; then
        cat "${arquivo}" 2>/dev/null
    else
        _r cat "${arquivo}" 2>/dev/null
    fi
}

_conf_ilegivel() {
    [[ -f "${MAIN_CONF}" ]] || return 1
    _cat_conf "${MAIN_CONF}" >/dev/null 2>&1 && return 1
    return 0
}

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

_valor_ativo() {
    local bruto valor
    bruto="$(_ler_chave "$1" "$2")"
    [[ -n "${bruto}" ]] || return 0
    valor="${bruto#*$'\t'}"
    printf '%s\n' "${valor:-(vazio)}"
    return 0
}

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

_BACKUP_FEITO=""

_copia_de_seguranca() {
    local origem="$1" rotulo="$2" backup ja
    _BACKUP_FEITO=""
    while IFS= read -r ja; do
        [[ -n "${ja}" ]] || continue
        if _r cmp -s "${origem}" "${ja}" 2>/dev/null; then
            _diz "este estado de $(basename "${origem}") já está guardado em ${ja} — sem backup novo"
            _BACKUP_FEITO="${ja}"
            return 0
        fi
    done < <(find "$(dirname "${origem}")" -maxdepth 1 -type f \
                  -name "$(basename "${origem}").bak.hefesto-*" ! -empty 2>/dev/null | sort)
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
    if ! novo="$(_r mktemp "${ETC}/.main.conf.hefesto-novo.XXXXXX" 2>/dev/null)"; then
        _erro "não consegui criar temporário em ${ETC} — NÃO mexi em ${MAIN_CONF}"
        return 1
    fi
    _lixo_add "${novo}"
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

_lista_backups() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
         ! -empty -printf '%T@\t%p\n' 2>/dev/null \
        | sort -rn -k1,1 -k2,2
    return 0
}

_lista_backups_vazios() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name 'main.conf.bak.hefesto-*' \
         -empty 2>/dev/null | sort
    return 0
}

_lista_orfaos() {
    [[ -d "${ETC}" ]] || return 0
    find "${ETC}" -maxdepth 1 -type f -name '.main.conf.hefesto-novo.*' \
         2>/dev/null | sort
    return 0
}

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
        [[ -n "${soma}" ]] || soma="ilegivel:${p}"
        somas+=("${soma}")
    done

    local -A estado_vivo=()
    for (( i = 0; i < total; i++ )); do
        if [[ "${i}" -lt "${BACKUPS_MANTER}" || "${i}" -eq $(( total - 1 )) ]]; then
            estado_vivo["${somas[i]}"]=1
        fi
    done

    local -A guardiao=()
    for (( i = total - 1; i >= 0; i-- )); do
        [[ "${i}" -ge "${BACKUPS_MANTER}" ]] || continue
        [[ "${i}" -ne $(( total - 1 )) ]] || continue
        [[ -z "${estado_vivo["${somas[i]}"]:-}" ]] || continue
        estado_vivo["${somas[i]}"]=1
        guardiao["${i}"]=1
    done

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

    if _conf_ilegivel; then
        _erro "não consigo LER ${MAIN_CONF} — sem leitura não sei o que estou reescrevendo, e não mexo"
        return 1
    fi

    anterior="$(_valor_ativo JustWorksRepairing "${MAIN_CONF}")"
    onde="$(_local_ativo JustWorksRepairing "${MAIN_CONF}")"
    if [[ -n "${anterior}" && "${anterior}" != "${VALOR_SEGURO}" ]]; then
        if [[ "${anterior}" == "never" ]]; then
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

    if [[ -d "${DROPIN_DIR}" ]]; then
        if _gravar_dropin "${ASSET_FAST}" "${DROPIN_FAST}" \
           && _gravar_dropin "${ASSET_JW}" "${DROPIN_JW}"; then
            _diz "drop-ins de main.conf.d gravados (mesmo valor do bloco: FastConnectable=true, JustWorksRepairing=${VALOR_SEGURO})"
        else
            _erro "drop-in de config do BlueZ falhou em ${DROPIN_DIR}"
            rc=1
        fi
    fi

    if [[ "${rc}" -eq 0 && "${sem_main_conf}" -eq 0 ]]; then
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

_remover() {
    local rc=0 tmp devolvido depois

    if _conf_ilegivel; then
        _erro "não consigo LER ${MAIN_CONF} — sem leitura não sei se há bloco nosso, e concluir que não há seria deixar o bloco no disco"
        return 1
    fi

    _remover_dropin "${ASSET_FAST}" "${DROPIN_FAST}" || rc=1
    _remover_dropin "${ASSET_JW}" "${DROPIN_JW}" || rc=1

    if [[ -f "${MAIN_CONF}" ]]; then
        if _tem_bloco_nosso || _cat_conf "${MAIN_CONF}" | grep -qF "${MARCA}"; then
            _avisar_alheio_no_bloco
            tmp="$(mktemp)"
            _lixo_add "${tmp}"
            if _despir_main_conf "${tmp}"; then
                devolvido="$(mktemp)"
                _lixo_add "${devolvido}"
                _r awk -v MARCA="${MARCA}" '
                    index($0, MARCA) == 1 { print substr($0, length(MARCA) + 1); next }
                    { print }
                ' "${tmp}" > "${devolvido}"
                mv -f "${devolvido}" "${tmp}"
                _lixo_tirar "${devolvido}"

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
