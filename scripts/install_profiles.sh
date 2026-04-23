#!/usr/bin/env bash
# install_profiles.sh — copia perfis default para ~/.config/hefesto/profiles/
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
readonly DEST_DIR="${HOME}/.config/hefesto/profiles"

if [[ ! -d "${SRC_DIR}" ]]; then
    printf 'ERRO: diretório de perfis não encontrado: %s\n' "${SRC_DIR}" >&2
    exit 1
fi

mkdir -p "${DEST_DIR}"

# Contar JSONs existentes no destino (excluindo meu_perfil.json para a lógica abaixo)
existing_count=$(find "${DEST_DIR}" -maxdepth 1 -name "*.json" ! -name "meu_perfil.json" | wc -l)

if [[ "${existing_count}" -eq 0 ]]; then
    # Primeira instalação: copiar todos os perfis default (exceto meu_perfil.json,
    # que tem tratamento especial abaixo).
    for src in "${SRC_DIR}"/*.json; do
        fname="$(basename "${src}")"
        if [[ "${fname}" == "meu_perfil.json" ]]; then
            continue
        fi
        cp -f "${src}" "${DEST_DIR}/${fname}"
        printf '      copiado: %s\n' "${fname}"
    done
else
    # Reinstalação: não sobrescrever perfis existentes.
    printf '      perfis já instalados — nenhum sobrescrito\n'
fi

# meu_perfil.json: sempre copiar SE AUSENTE.
readonly MEU_PERFIL_SRC="${SRC_DIR}/meu_perfil.json"
readonly MEU_PERFIL_DEST="${DEST_DIR}/meu_perfil.json"

if [[ ! -f "${MEU_PERFIL_DEST}" ]]; then
    if [[ -f "${MEU_PERFIL_SRC}" ]]; then
        cp -f "${MEU_PERFIL_SRC}" "${MEU_PERFIL_DEST}"
        printf '      copiado: meu_perfil.json (slot do usuário criado)\n'
    fi
else
    printf '      meu_perfil.json já existe — preservado\n'
fi
