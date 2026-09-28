#!/usr/bin/env bash
# p1-lar-vazio.sh — o degrau P1 da escada da máquina limpa: o ENSAIO do
# install.sh num HOME vazio. Muda uma variável só: o HOME.
#
# O-PRODUTO-EM-QUALQUER-MAQUINA-01 (28/09/2026), a Parte A. O roteiro morava
# num estudo fora do git, e um roteiro que não viaja com a árvore não chega a
# quem vai reproduzir. O que este degrau alcança: o plano de usuária que uma
# pessoa nova recebe (a .venv, os links, as units de usuário, o wrapper) e a
# prova de que o ensaio não escreve nada. O que ele NÃO alcança: os passos de
# root dizem o estado DESTA máquina (DKMS, BlueZ, udev), e isso é limite do
# degrau, não defeito — quem mede o sistema inteiro é o P4.
#
# AS TRAVAS, e nenhuma é opcional:
#   - o install roda SEMPRE com --dry-run; não há flag que tire isso;
#   - o HOME e os cinco XDG_* apontam para um lar novo, e há guarda que SAI se
#     o HOME não for o lar (o shell desta casa é zsh, e um `env $E` sem aspas
#     já desviou só o HOME uma vez);
#   - sem DBUS, WAYLAND e DISPLAY: nada fala com a sessão de quem roda;
#   - nunca como root (com root o HOME vira /root);
#   - a árvore é uma CÓPIA (`git archive`), nunca a árvore de trabalho;
#   - a config de quem roda só é LIDA por sha256, antes e depois, para provar
#     que ficou intacta.
#
# Uso:
#   bash scripts/maquina-limpa/p1-lar-vazio.sh [--saida DIR] [--ref REF]
#
# Espera-se: rc=0 e o «FIM DO ENSAIO»; ZERO arquivos no lar; «config intacta».
# O código de saída é 0 só com os três.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SAIDA="${TMPDIR:-/tmp}/hefesto-maquina-limpa/p1"
REF="HEAD"

while (( $# )); do
    case "$1" in
        --saida) SAIDA="$2"; shift 2 ;;
        --ref)   REF="$2"; shift 2 ;;
        -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) printf 'argumento desconhecido: %s\n' "$1" >&2; exit 2 ;;
    esac
done

[[ "$(id -u)" -ne 0 ]] || { echo "P1 não roda como root: o HOME viraria /root" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "falta o git" >&2; exit 2; }

CASA_REAL="$(getent passwd "$(id -un)" | cut -d: -f6)"
CONFIG_REAL="${CASA_REAL}/.config/hefesto-dualsense4unix"

mkdir -p "${SAIDA}"
ARVORE="${SAIDA}/arvore"
LAR="${SAIDA}/lar"
rm -rf "${ARVORE}" "${LAR}"
mkdir -p "${ARVORE}"
git -C "${RAIZ}" archive "${REF}" | tar -x -C "${ARVORE}"

_sha_da_config() {
    [[ -d "${CONFIG_REAL}" ]] || { echo "(sem config)"; return 0; }
    find "${CONFIG_REAL}" -type f -name '*.json' -print0 2>/dev/null \
        | sort -z | xargs -0 -r sha256sum
}
_sha_da_config > "${SAIDA}/config-antes.sha"

# O ensaio num processo próprio: o ambiente desviado não vaza para este shell.
bash -s -- "${ARVORE}" "${LAR}" > "${SAIDA}/p1.txt" 2>&1 <<'DENTRO' || true
set -u
ARVORE="$1"; LAR="$2"
mkdir -p "${LAR}/.config" "${LAR}/.local/share" "${LAR}/.local/state" "${LAR}/.cache" "${LAR}/run"
chmod 700 "${LAR}/run"
export HOME="${LAR}"
export XDG_CONFIG_HOME="${LAR}/.config"
export XDG_DATA_HOME="${LAR}/.local/share"
export XDG_STATE_HOME="${LAR}/.local/state"
export XDG_CACHE_HOME="${LAR}/.cache"
export XDG_RUNTIME_DIR="${LAR}/run"
unset DBUS_SESSION_BUS_ADDRESS WAYLAND_DISPLAY DISPLAY
[[ "${HOME}" == "${LAR}" && "${XDG_CONFIG_HOME}" == "${LAR}/.config" ]] \
    || { echo "GUARDA: o HOME não desviou — nada roda"; exit 1; }
cd "${ARVORE}" || exit 1
antes="$(find "${LAR}" -type f | wc -l)"
bash ./install.sh --dry-run --yes
echo "rc=$?"
depois="$(find "${LAR}" -type f | wc -l)"
echo "arquivos_no_lar=$(( depois - antes ))"
find "${LAR}" -type f -newer "${ARVORE}/install.sh" | sed "s#${LAR}#<lar>#"
DENTRO

_sha_da_config > "${SAIDA}/config-depois.sha"
if cmp -s "${SAIDA}/config-antes.sha" "${SAIDA}/config-depois.sha"; then
    echo "config intacta" >> "${SAIDA}/p1.txt"
else
    echo "CONFIG MUDOU durante o ensaio" >> "${SAIDA}/p1.txt"
fi

rc="$(sed -n 's/^rc=//p' "${SAIDA}/p1.txt" | tail -1)"
arquivos="$(sed -n 's/^arquivos_no_lar=//p' "${SAIDA}/p1.txt" | tail -1)"
printf 'P1: rc=%s · arquivos no lar=%s · %s\n' "${rc:-?}" "${arquivos:-?}" \
    "$(tail -1 "${SAIDA}/p1.txt")"
printf 'relato completo: %s\n' "${SAIDA}/p1.txt"
[[ "${rc:-1}" == "0" && "${arquivos:-1}" == "0" ]] && grep -q '^config intacta$' "${SAIDA}/p1.txt"
