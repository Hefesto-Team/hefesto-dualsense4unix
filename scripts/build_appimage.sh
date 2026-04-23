#!/usr/bin/env bash
# Gera AppImage do Hefesto via python-appimage (opcional).
#
# Pré-requisitos:
#   sudo apt install libfuse2 librsvg2-bin
#   pip install python-appimage build
#
# Uso:
#   ./scripts/build_appimage.sh              # Python 3.12 por padrão
#   PYTHON_VERSION=3.11 ./scripts/build_appimage.sh
#
# Saída: dist/appimage/Hefesto-<version>-x86_64.AppImage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
APPDIR_SRC="$HERE/assets/appimage"
WORK_DIR="$HERE/build/appimage"
OUT_DIR="$HERE/dist/appimage"

if ! command -v python-appimage >/dev/null 2>&1; then
    echo "erro: python-appimage não instalado. Execute:"
    echo "  pip install python-appimage"
    exit 2
fi

# Converte SVG -> PNG (AppImage exige PNG).
if [[ ! -f "$APPDIR_SRC/Hefesto.png" ]]; then
    echo "[1/4] Gerando Hefesto.png do SVG..."
    if command -v rsvg-convert >/dev/null 2>&1; then
        rsvg-convert -w 256 -h 256 "$APPDIR_SRC/Hefesto.svg" \
            -o "$APPDIR_SRC/Hefesto.png"
    elif command -v convert >/dev/null 2>&1; then
        convert -background none -size 256x256 "$APPDIR_SRC/Hefesto.svg" \
            "$APPDIR_SRC/Hefesto.png"
    else
        echo "erro: instale rsvg-convert (sudo apt install librsvg2-bin)"
        exit 3
    fi
fi

# Garante que há um wheel atualizado.
if ! ls "$HERE/dist"/hefesto-*.whl >/dev/null 2>&1; then
    echo "[2/4] Nenhum wheel em dist/. Buildando..."
    python -m build --wheel
fi

# Copia appdir e aponta requirements pro wheel local (offline).
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp -r "$APPDIR_SRC/." "$WORK_DIR/"
chmod +x "$WORK_DIR/entrypoint.sh"

WHEEL=$(ls -t "$HERE/dist"/hefesto-*.whl | head -1)
cat > "$WORK_DIR/requirements.txt" <<EOF
$WHEEL
EOF

mkdir -p "$OUT_DIR"
# Le versão do pyproject.toml (Python 3.11+ tem tomllib nativo; fallback tomli)
# Mesmo padrão de build_deb.sh — zero dependência de `import hefesto` funcionar.
VERSION=$(python3 - <<'EOF'
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
print(data["project"]["version"])
EOF
)
OUT_FILE="$OUT_DIR/Hefesto-${VERSION}-x86_64.AppImage"
echo "Versão detectada: ${VERSION}"

echo "[3/4] Gerando AppImage com Python ${PYTHON_VERSION}..."
python-appimage build app \
    --python-version "$PYTHON_VERSION" \
    --linux-tag "manylinux2014_x86_64" \
    --name Hefesto \
    "$WORK_DIR"

# python-appimage cria no cwd com nome Hefesto-x86_64.AppImage
if [[ -f "$HERE/Hefesto-x86_64.AppImage" ]]; then
    mv "$HERE/Hefesto-x86_64.AppImage" "$OUT_FILE"
fi

if [[ -f "$OUT_FILE" ]]; then
    chmod +x "$OUT_FILE"
    echo "[4/4] AppImage pronto:"
    ls -lh "$OUT_FILE"
    echo ""
    echo "Teste: $OUT_FILE version"
else
    echo "aviso: arquivo final não encontrado; veja logs do python-appimage."
    exit 4
fi

# "A obra prova o mestre." — Sabedoria popular
