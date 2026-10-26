#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${REPO_ROOT}/flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
APP_ID="io.github.hefesto_team.hefesto_dualsense4unix"
BUILD_DIR="${REPO_ROOT}/flatpak-build-dir"
REPO_DIR="${REPO_ROOT}/flatpak-repo"

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

if [[ "$INSTALAR" == "true" ]]; then
  echo ""
  echo "==> Instalando ${APP_ID} no repositório local do usuário..."
  flatpak --user remote-add --if-not-exists \
    hefesto-dualsense4unix-local-repo "${REPO_DIR}" 2>/dev/null || true
  flatpak --user install --reinstall -y \
    hefesto-dualsense4unix-local-repo "${APP_ID}"
  echo "  Instalado. Execute com: flatpak run ${APP_ID}"
fi

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
