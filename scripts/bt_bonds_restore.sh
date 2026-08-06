#!/usr/bin/env bash
# bt_bonds_restore.sh — restauração MANUAL de um snapshot de bonds do BlueZ.
#
# Por que manual (sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md,
# camada 2, risco B): se o CONTROLE já rotacionou a própria chave (ele
# "esqueceu" o bond — cenário já medido nesta máquina), restaurar cegamente a
# LinkKey antiga do lado do PC produz uma chave que o peer rejeita → loop de
# falha de autenticação, exatamente a classe de gatilho do crash de heap.
# Então: o doctor DETECTA e SUGERE; quem decide restaurar é o humano.
#
# Uso:
#   bt_bonds_restore.sh --list           lista snapshots disponíveis
#   bt_bonds_restore.sh --verificar <ts> valida um snapshot SEM restaurar nada
#   bt_bonds_restore.sh --latest         restaura o snapshot mais recente
#   bt_bonds_restore.sh <timestamp>      restaura um snapshot específico
#
# O restore: para o bluetooth.service, MESCLA os diretórios de device do
# snapshot em /var/lib/bluetooth (sem apagar nada que exista), religa o
# serviço. Se um controle restaurado recusar conexão depois ("chave velha"),
# remova só ele (bluetoothctl remove <MAC>) e re-pareie com Pair() explícito.
#
# RADIO-ABERTO-01/E10 (05/08/2026) — POR QUE A VALIDAÇÃO EXISTE:
# este script copiava o diretório do device com `cp -a`, que **preserva
# symlinks em vez de segui-los**. Um snapshot preparado contendo
#   <adaptador>/<MAC>/info -> /etc/sudoers.d/x
# era copiado tal e qual para /var/lib/bluetooth, e o bluetoothd — que roda
# como ROOT — passava a escrever ATRAVÉS do link. Isso é escrita arbitrária
# como root a partir de um snapshot.
# Hoje o acervo é local e só o root escreve nele, o que limita o alcance; mas
# a BONDS-QUE-SOBREVIVEM-01 quer ACIONAR a restauração automaticamente, e
# qualquer futuro que inclua importar/sincronizar snapshot transforma isto em
# execução remota. A validação roda ANTES de parar o serviço: um snapshot
# recusado não custa a ela os controles conectados.
set -euo pipefail

# Overrides de teste (test_radio_aberto_e10.py). Em produção ficam nos padrões:
# o script roda como root a partir da unit/doctor, sem env nenhuma.
SRC_ROOT="${HEFESTO_BT_BONDS_SRC:-/var/lib/hefesto-dualsense4unix/bt-bonds}"
DST="${HEFESTO_BT_DST:-/var/lib/bluetooth}"

#: Nomes de ARQUIVO aceitos dentro do diretório de um device. Qualquer outro é
#: recusado — lista explícita, e não "tudo menos o que eu lembrei de barrar".
_ARQUIVOS_DE_DEVICE_OK=" info attributes "
#: Idem, no diretório do adaptador (fora dos diretórios de device e do cache).
_ARQUIVOS_DE_ADAPTADOR_OK=" settings attributes cache "

#: MAC do BlueZ no nome de diretório/arquivo: AA:BB:CC:DD:EE:FF.
_MAC_RE='^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'

_recusa() {
    printf 'bt_bonds_restore.sh: RECUSADO — %s\n' "$1" >&2
    printf '   (RADIO-ABERTO-01/E10: um snapshot só é restaurado se cada entrada\n' >&2
    printf '    for arquivo ou diretório comum, com nome esperado. Nada de symlink.)\n' >&2
}

# Valida uma entrada qualquer: recusa symlink, device, socket, FIFO e hardlink.
# `cp -a` copiaria o symlink como symlink; o bluetoothd escreveria através dele.
_entrada_comum_ok() {
    local caminho="$1" rotulo="$2"
    if [[ -L "${caminho}" ]]; then
        _recusa "${rotulo} é um SYMLINK (${caminho} -> $(readlink "${caminho}" 2>/dev/null))"
        return 1
    fi
    if [[ -d "${caminho}" ]]; then
        return 0
    fi
    if [[ ! -f "${caminho}" ]]; then
        _recusa "${rotulo} não é arquivo comum nem diretório (${caminho})"
        return 1
    fi
    # Hardlink para fora da árvore: o conteúdo é o mesmo inode, e escrever nele
    # escreve no alvo. Um arquivo de bond legítimo nunca tem nlink > 1.
    local nlink
    nlink="$(stat -c '%h' "${caminho}" 2>/dev/null || echo 1)"
    if [[ "${nlink}" -gt 1 ]]; then
        _recusa "${rotulo} tem ${nlink} hardlinks (${caminho})"
        return 1
    fi
    return 0
}

# Percorre o snapshot inteiro e recusa o que não for esperado. Não copia nada.
_validar_snapshot() {
    local snap="$1" problemas=0 adapter base dev devbase arquivo nome entry
    while IFS= read -r -d '' adapter; do
        base="$(basename "${adapter}")"
        _entrada_comum_ok "${adapter}" "adaptador '${base}'" || { problemas=1; continue; }
        if [[ ! "${base}" =~ ${_MAC_RE} ]]; then
            _recusa "nome de adaptador não é um MAC: '${base}'"
            problemas=1
            continue
        fi
        while IFS= read -r -d '' entry; do
            nome="$(basename "${entry}")"
            _entrada_comum_ok "${entry}" "'${base}/${nome}'" || { problemas=1; continue; }
            if [[ -d "${entry}" ]]; then
                # Diretório: ou é o cache, ou é um device (nome = MAC).
                if [[ "${nome}" != "cache" && ! "${nome}" =~ ${_MAC_RE} ]]; then
                    _recusa "diretório inesperado em '${base}': '${nome}'"
                    problemas=1
                    continue
                fi
                while IFS= read -r -d '' arquivo; do
                    devbase="$(basename "${arquivo}")"
                    _entrada_comum_ok "${arquivo}" "'${base}/${nome}/${devbase}'" \
                        || { problemas=1; continue; }
                    if [[ -d "${arquivo}" ]]; then
                        _recusa "subdiretório inesperado em '${base}/${nome}': '${devbase}'"
                        problemas=1
                        continue
                    fi
                    if [[ "${nome}" == "cache" ]]; then
                        [[ "${devbase}" =~ ${_MAC_RE} ]] && continue
                        _recusa "entrada de cache com nome que não é MAC: '${devbase}'"
                        problemas=1
                    else
                        [[ "${_ARQUIVOS_DE_DEVICE_OK}" == *" ${devbase} "* ]] && continue
                        _recusa "arquivo inesperado em '${base}/${nome}': '${devbase}'"
                        problemas=1
                    fi
                done < <(find "${entry}" -mindepth 1 -maxdepth 1 -print0)
            else
                if [[ "${_ARQUIVOS_DE_ADAPTADOR_OK}" != *" ${nome} "* ]]; then
                    _recusa "arquivo inesperado em '${base}': '${nome}'"
                    problemas=1
                fi
            fi
        done < <(find "${adapter}" -mindepth 1 -maxdepth 1 -print0)
    done < <(find "${snap}" -mindepth 1 -maxdepth 1 -print0)
    return "${problemas}"
}

# `--list` e `--verificar` só LEEM: não param serviço, não tocam o storage e
# não precisam de root (o acervo em /var/lib costuma exigir, mas isso é do
# caminho, não do modo — e é o que torna a validação da E10 testável).
case "${1:-}" in
    --list|--verificar) ;;
    *)
        if [[ "$(id -u)" -ne 0 ]]; then
            printf 'bt_bonds_restore.sh: requer root\n' >&2
            exit 1
        fi
        ;;
esac

usage() { sed -n '12,16p' "$0"; exit 1; }

ARG="${1:-}"
[[ -z "${ARG}" ]] && usage

if [[ "${ARG}" == "--list" ]]; then
    if [[ ! -d "${SRC_ROOT}" ]]; then
        printf 'nenhum snapshot (diretório %s ausente)\n' "${SRC_ROOT}"
        exit 0
    fi
    find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | while read -r TS; do
        N="$(find "${SRC_ROOT}/${TS}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
        printf '%s  (%s bond(s))\n' "${TS}" "${N}"
    done
    exit 0
fi

SO_VERIFICAR=0
if [[ "${ARG}" == "--verificar" ]]; then
    SO_VERIFICAR=1
    ARG="${2:---latest}"
fi

if [[ "${ARG}" == "--latest" ]]; then
    SNAP="$(find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)"
    [[ -z "${SNAP}" ]] && { printf 'nenhum snapshot disponível em %s\n' "${SRC_ROOT}" >&2; exit 1; }
else
    SNAP="${SRC_ROOT}/${ARG}"
    [[ -d "${SNAP}" ]] || { printf 'snapshot %s não existe (use --list)\n' "${ARG}" >&2; exit 1; }
fi

# RADIO-ABERTO-01/E10: valida ANTES de qualquer coisa — antes de parar o
# serviço, antes de tocar no storage. Um snapshot recusado não custa a ela os
# controles conectados, e nenhum byte dele chega a /var/lib/bluetooth.
if ! _validar_snapshot "${SNAP}"; then
    printf 'bt_bonds_restore.sh: snapshot %s REPROVADO na validação — nada foi restaurado\n' \
        "${SNAP}" >&2
    exit 1
fi

if [[ "${SO_VERIFICAR}" -eq 1 ]]; then
    printf 'snapshot %s: validação OK (nada foi restaurado — modo --verificar)\n' "${SNAP}"
    exit 0
fi

N="$(find "${SNAP}" -mindepth 3 -maxdepth 3 -type f -name info 2>/dev/null | wc -l)"
if [[ "${N}" -eq 0 ]]; then
    printf 'snapshot %s não tem nenhum bond — nada a restaurar\n' "${SNAP}" >&2
    exit 1
fi

printf '>>> restaurando %s bond(s) de %s\n' "${N}" "${SNAP}"
printf '>>> o bluetooth.service vai ser PARADO durante a cópia (controles BT caem)\n'
printf '>>> se um controle recusar conexão depois: bluetoothctl remove <MAC> e re-pareie\n'

# RESTORE-MASK-01 (23/07, medido ao vivo): o bluetooth.service é ativável por
# D-Bus — qualquer cliente consultando org.bluez (GUI, applet, daemon) dispara
# uma bus-activation que CANCELA o job de stop ("Job for bluetooth.service
# canceled") e o restore aborta silencioso pelo set -e, com o serviço vivo e o
# storage sendo mexido por baixo dele. O mask --runtime fecha a janela: com a
# unit mascarada a activation falha na hora e o stop conclui de verdade.
systemctl mask --runtime bluetooth.service >/dev/null 2>&1 || true
trap 'systemctl unmask --runtime bluetooth.service >/dev/null 2>&1 || true; systemctl start bluetooth.service' EXIT
systemctl stop --job-mode=replace-irreversibly bluetooth.service
for _i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    systemctl is-active --quiet bluetooth.service || break
    sleep 5
done
if systemctl is-active --quiet bluetooth.service; then
    printf 'bt_bonds_restore.sh: bluetooth.service não parou (60s) — abortando sem mexer no storage\n' >&2
    exit 1
fi

# Mescla sem destruir: copia adaptador/device do snapshot por cima; o que já
# existe no destino e não existe no snapshot fica intocado.
while IFS= read -r -d '' ADAPTER; do
    BASE="$(basename "${ADAPTER}")"
    install -d -m 700 "${DST}/${BASE}"
    find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type f -exec cp -a {} "${DST}/${BASE}/" \;
    while IFS= read -r -d '' DEVDIR; do
        DEVBASE="$(basename "${DEVDIR}")"
        [[ "${DEVBASE}" == "cache" ]] && continue
        # RADIO-ABERTO-01/E10: era `cp -a "${DEVDIR}"` — a cópia RECURSIVA do
        # diretório, que preserva symlinks lá dentro. `_validar_snapshot` já
        # recusaria o snapshot, mas a cópia também passou a ser por CONTEÚDO,
        # arquivo a arquivo do conjunto esperado: defesa em profundidade, e o
        # que sai daqui não depende de a validação ter enxergado tudo.
        install -d -m 700 "${DST}/${BASE}/${DEVBASE}"
        find "${DEVDIR}" -mindepth 1 -maxdepth 1 -type f \
            \( -name info -o -name attributes \) \
            -exec cp -a {} "${DST}/${BASE}/${DEVBASE}/" \;
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
    # cache/ (SDP-CACHE-01): restaurar o registro SDP é o que faz o perfil HID
    # subir sem re-pareamento. Mas NUNCA sobrescrever um registro bom com um
    # envenenado — uma entrada sem [ServiceRecords] é exatamente o estado que
    # produz o controle zumbi (ACL vivo, zero hidraw). Snapshots feitos antes
    # do SDP-CACHE-01 não têm cache nenhum: aí este bloco é no-op.
    if [[ -d "${ADAPTER}/cache" ]]; then
        install -d -m 700 "${DST}/${BASE}/cache"
        while IFS= read -r -d '' ENTRY; do
            MAC="$(basename "${ENTRY}")"
            if ! grep -q '^\[ServiceRecords\]' "${ENTRY}" 2>/dev/null; then
                printf '   cache SDP de %s no snapshot está sem [ServiceRecords] — não restaurado\n' "${MAC}"
                continue
            fi
            cp -a "${ENTRY}" "${DST}/${BASE}/cache/"
        done < <(find "${ADAPTER}/cache" -mindepth 1 -maxdepth 1 -type f -print0)
    fi
done < <(find "${SNAP}" -mindepth 1 -maxdepth 1 -type d -print0)

chmod -R go-rwx "${DST}"
printf 'restaurado. religando o bluetooth.service...\n'
exit 0
