#!/usr/bin/env bash
# install_profiles.sh — copia perfis default para ~/.config/hefesto-dualsense4unix/profiles/
#
# Regras:
#   - Se o diretório de perfis estiver VAZIO (primeira instalação), copia
#     todos os JSONs de assets/profiles_default/.
#   - Se já houver perfis (reinstalação), NÃO sobrescreve nenhum existente.
#   - EXCEÇÃO: meu_perfil.json é sempre copiado SE AUSENTE (slot do usuário
#     deve sempre existir), mas nunca sobrescrito se já existe.
#
# Uso:
#   ./scripts/install_profiles.sh [ROOT_DIR]
#
# ROOT_DIR: raiz do repositório (default: diretório pai deste script).

set -euo pipefail

ROOT_DIR="${1:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}"
readonly SRC_DIR="${ROOT_DIR}/assets/profiles_default"
readonly DEST_DIR="${HOME}/.config/hefesto-dualsense4unix/profiles"

if [[ ! -d "${SRC_DIR}" ]]; then
    printf 'ERRO: diretório de perfis não encontrado: %s\n' "${SRC_DIR}" >&2
    exit 1
fi

mkdir -p "${DEST_DIR}"

# INSTALL-PROFILES-COPY-IF-ABSENT-01: copia cada preset default AUSENTE no
# destino — nunca sobrescreve um perfil existente (preserva edições da usuária).
# Antes só copiava quando o dir estava 100% VAZIO, então presets NOVOS (ex.:
# point_and_click da V3.11) nunca chegavam num upgrade — a feature nascia morta.
#
# INSTALL-PROFILES-RESPECT-DELETION-01: um marker `.seeded_presets` registra os
# presets já semeados. Assim, um preset que a usuária DELETA de propósito NÃO é
# ressuscitado numa reinstalação (a cópia cega copy-if-absent o traria de volta).
# Regra: só copia se AUSENTE E ainda-não-semeado; presets já presentes na 1ª
# execução (perfis da v3.10) são registrados sem cópia, então deleções POSTERIORES
# passam a ser respeitadas.
readonly MARKER="${DEST_DIR}/.seeded_presets"
touch "${MARKER}"
copied=0
for src in "${SRC_DIR}"/*.json; do
    fname="$(basename "${src}")"
    dest="${DEST_DIR}/${fname}"
    # Já semeado antes → respeita a decisão da usuária (inclusive deletar).
    if grep -qxF "${fname}" "${MARKER}"; then
        continue
    fi
    if [[ -f "${dest}" ]]; then
        # Presente na 1ª execução (v3.10/editado): registra sem copiar.
        printf '%s\n' "${fname}" >> "${MARKER}"
        continue
    fi
    cp -f "${src}" "${dest}"
    printf '%s\n' "${fname}" >> "${MARKER}"
    if [[ "${fname}" == "meu_perfil.json" ]]; then
        printf '      copiado: meu_perfil.json (slot do usuário criado)\n'
    else
        printf '      copiado: %s\n' "${fname}"
    fi
    copied=$((copied + 1))
done

if [[ "${copied}" -eq 0 ]]; then
    printf '      todos os perfis default já presentes/semeados — nenhum copiado\n'
fi
