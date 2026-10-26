#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${1:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}"
readonly SRC_DIR="${ROOT_DIR}/assets/profiles_default"
readonly DEST_DIR="${HOME}/.config/hefesto-dualsense4unix/profiles"

if [[ ! -d "${SRC_DIR}" ]]; then
    printf 'ERRO: diretório de perfis não encontrado: %s\n' "${SRC_DIR}" >&2
    exit 1
fi

mkdir -p "${DEST_DIR}"

readonly MARKER="${DEST_DIR}/.seeded_presets"
touch "${MARKER}"
copied=0
for src in "${SRC_DIR}"/*.json; do
    fname="$(basename "${src}")"
    dest="${DEST_DIR}/${fname}"
    if grep -qxF "${fname}" "${MARKER}"; then
        continue
    fi
    if [[ "${fname}" == "freestyle.json" && ( -f "${DEST_DIR}/meu_perfil.json" || -f "${DEST_DIR}/personalizado.json" ) ]]; then
        printf '%s\n' "${fname}" >> "${MARKER}"
        continue
    fi
    if [[ -f "${dest}" ]]; then
        printf '%s\n' "${fname}" >> "${MARKER}"
        continue
    fi
    cp -f "${src}" "${dest}"
    printf '%s\n' "${fname}" >> "${MARKER}"
    if [[ "${fname}" == "freestyle.json" ]]; then
        printf '      copiado: freestyle.json (slot do usuário criado)\n'
    else
        printf '      copiado: %s\n' "${fname}"
    fi
    copied=$((copied + 1))
done

if [[ "${copied}" -eq 0 ]]; then
    printf '      todos os perfis default já presentes/semeados — nenhum copiado\n'
fi
