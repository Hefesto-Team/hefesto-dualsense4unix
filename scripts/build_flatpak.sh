#!/usr/bin/env bash
# build_flatpak.sh — Constrói e empacota o Hefesto - Dualsense4Unix como Flatpak
#
# Uso:
#   ./scripts/build_flatpak.sh [--install] [--bundle]
#
# Opções:
#   --install   Instala o Flatpak no repositório local do usuário após o build
#   --bundle    Exporta arquivo .flatpak para distribuição offline
#
# Pré-requisitos:
#   - flatpak-builder  (sudo apt install flatpak-builder  OU  flatpak install flathub org.flatpak.Builder)
#   - python -m build  (pip install build)
#   - Runtime GNOME//45 adicionado ao Flatpak:
#       flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
#       flatpak install flathub org.gnome.Platform//45 org.gnome.Sdk//45

set -euo pipefail

# Raiz do repositório (relativa ao script)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${REPO_ROOT}/flatpak/br.andrefarias.Hefesto.yml"
APP_ID="br.andrefarias.Hefesto"
BUILD_DIR="${REPO_ROOT}/flatpak-build-dir"
REPO_DIR="${REPO_ROOT}/flatpak-repo"

# Flags de linha de comando
INSTALAR=false
BUNDLE=false

for arg in "$@"; do
  case "$arg" in
    --install) INSTALAR=true ;;
    --bundle)  BUNDLE=true ;;
    *)
      echo "ERRO: argumento desconhecido: $arg"
      echo "Uso: $0 [--install] [--bundle]"
      exit 1
      ;;
  esac
done

# Verificar pré-requisitos
if ! command -v flatpak-builder &>/dev/null; then
  echo "ERRO: flatpak-builder não encontrado."
  echo "Instale com: sudo apt install flatpak-builder"
  echo "  ou: flatpak install flathub org.flatpak.Builder"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "ERRO: python3 não encontrado."
  exit 1
fi

# ── Passo 1: Construir o wheel Python ──────────────────────────────────────────
echo ""
echo "==> Construindo wheel Python..."
cd "${REPO_ROOT}"

if ! python3 -c "import build" &>/dev/null; then
  echo "ERRO: módulo 'build' não encontrado. Execute: pip install build"
  exit 1
fi

rm -rf "${REPO_ROOT}/dist"
python3 -m build --wheel --outdir "${REPO_ROOT}/dist"
WHEEL_PATH=$(ls "${REPO_ROOT}/dist/"*.whl 2>/dev/null | head -1)

if [[ -z "$WHEEL_PATH" ]]; then
  echo "ERRO: nenhum .whl gerado em dist/"
  exit 1
fi

echo "  Wheel gerado: ${WHEEL_PATH}"

# ── Passo 2: Construir o Flatpak ───────────────────────────────────────────────
echo ""
echo "==> Construindo Flatpak via flatpak-builder..."
echo "    Manifest: ${MANIFEST}"
echo "    Diretório de build: ${BUILD_DIR}"

flatpak-builder \
  --user \
  --install-deps-from=flathub \
  --force-clean \
  --repo="${REPO_DIR}" \
  "${BUILD_DIR}" \
  "${MANIFEST}"

echo "  Build concluído."

# ── Passo 3 (opcional): Instalar no repositório local do usuário ───────────────
if [[ "$INSTALAR" == "true" ]]; then
  echo ""
  echo "==> Instalando ${APP_ID} no repositório local do usuário..."
  flatpak --user remote-add --if-not-exists \
    hefesto-dualsense4unix-local-repo "${REPO_DIR}" 2>/dev/null || true
  flatpak --user install --reinstall -y \
    hefesto-dualsense4unix-local-repo "${APP_ID}"
  echo "  Instalado. Execute com: flatpak run ${APP_ID}"
fi

# ── Passo 4 (opcional): Exportar bundle .flatpak ──────────────────────────────
if [[ "$BUNDLE" == "true" ]]; then
  echo ""
  BUNDLE_OUT="${REPO_ROOT}/${APP_ID}.flatpak"
  echo "==> Exportando bundle: ${BUNDLE_OUT}"
  flatpak build-bundle \
    "${REPO_DIR}" \
    "${BUNDLE_OUT}" \
    "${APP_ID}"
  echo "  Bundle gerado: ${BUNDLE_OUT}"
  echo "  Instale com: flatpak install --user ${BUNDLE_OUT}"
fi

echo ""
echo "==> Concluído."
echo ""
echo "  Para instalar udev rules no host (necessário uma vez):"
echo "    flatpak run --command=install-host-udev.sh ${APP_ID}"
