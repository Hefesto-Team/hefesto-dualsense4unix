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
#   bt_bonds_restore.sh --latest         restaura o snapshot mais recente
#   bt_bonds_restore.sh <timestamp>      restaura um snapshot específico
#
# O restore: para o bluetooth.service, MESCLA os diretórios de device do
# snapshot em /var/lib/bluetooth (sem apagar nada que exista), religa o
# serviço. Se um controle restaurado recusar conexão depois ("chave velha"),
# remova só ele (bluetoothctl remove <MAC>) e re-pareie com Pair() explícito.
set -euo pipefail

SRC_ROOT=/var/lib/hefesto-dualsense4unix/bt-bonds
DST=/var/lib/bluetooth

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'bt_bonds_restore.sh: requer root\n' >&2
    exit 1
fi

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

if [[ "${ARG}" == "--latest" ]]; then
    SNAP="$(find "${SRC_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)"
    [[ -z "${SNAP}" ]] && { printf 'nenhum snapshot disponível em %s\n' "${SRC_ROOT}" >&2; exit 1; }
else
    SNAP="${SRC_ROOT}/${ARG}"
    [[ -d "${SNAP}" ]] || { printf 'snapshot %s não existe (use --list)\n' "${ARG}" >&2; exit 1; }
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
        cp -a "${DEVDIR}" "${DST}/${BASE}/"
    done < <(find "${ADAPTER}" -mindepth 1 -maxdepth 1 -type d -print0)
done < <(find "${SNAP}" -mindepth 1 -maxdepth 1 -type d -print0)

chmod -R go-rwx "${DST}"
printf 'restaurado. religando o bluetooth.service...\n'
exit 0
