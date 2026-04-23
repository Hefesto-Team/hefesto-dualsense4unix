#!/usr/bin/env bash
# build_deb.sh — Gera pacote .deb para o Hefesto usando dpkg-deb --build.
# Não usa dh_python3 nem dpkg-buildpackage; funciona em qualquer sistema
# com dpkg-deb instalado (Ubuntu/Debian padrão).
#
# Uso: bash scripts/build_deb.sh [--output-dir <dir>]
# Saida: dist/hefesto_<version>_amd64.deb

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Le versao do pyproject.toml (Python 3.11+ tem tomllib nativo; fallback tomli)
# ---------------------------------------------------------------------------
VERSION=$(python3 - <<'EOF'
import sys
try:
    import tomllib
    open_mode = "rb"
except ImportError:
    try:
        import tomli as tomllib
        open_mode = "rb"
    except ImportError:
        sys.exit("Erro: tomllib (Python 3.11+) ou tomli não encontrado. Instale: pip install tomli")
with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
print(data["project"]["version"])
EOF
)

echo "Versao detectada: ${VERSION}"

# ---------------------------------------------------------------------------
# Diretório de staging temporário
# ---------------------------------------------------------------------------
STAGING=$(mktemp -d /tmp/hefesto_deb_XXXXXX)
trap 'rm -rf "$STAGING"' EXIT

echo "Staging: ${STAGING}"

# Estrutura de diretórios dentro do pacote
mkdir -p \
    "${STAGING}/DEBIAN" \
    "${STAGING}/usr/bin" \
    "${STAGING}/usr/lib/python3/dist-packages" \
    "${STAGING}/usr/lib/udev/rules.d" \
    "${STAGING}/usr/lib/systemd/user" \
    "${STAGING}/usr/share/applications" \
    "${STAGING}/usr/share/hefesto/assets" \
    "${STAGING}/usr/share/icons/hicolor/256x256/apps"

# ---------------------------------------------------------------------------
# Copiar pacote Python
# ---------------------------------------------------------------------------
echo "Copiando src/hefesto/ ..."
cp -r src/hefesto "${STAGING}/usr/lib/python3/dist-packages/hefesto"

# Remover __pycache__ do pacote
find "${STAGING}/usr/lib/python3/dist-packages/hefesto" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${STAGING}/usr/lib/python3/dist-packages/hefesto" -name '*.pyc' -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# Copiar assets
# ---------------------------------------------------------------------------
echo "Copiando assets/ ..."
cp -r assets/. "${STAGING}/usr/share/hefesto/assets/"

# Icone principal (usa o da pasta appimage que e o mais completo)
if [ -f "assets/appimage/Hefesto.png" ]; then
    cp "assets/appimage/Hefesto.png" "${STAGING}/usr/share/icons/hicolor/256x256/apps/hefesto.png"
fi

# ---------------------------------------------------------------------------
# Copiar regras udev
# ---------------------------------------------------------------------------
echo "Copiando regras udev ..."
for rules_file in assets/70-*.rules assets/71-*.rules assets/72-*.rules assets/73-*.rules assets/74-*.rules; do
    [ -f "$rules_file" ] && cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"
done

# ---------------------------------------------------------------------------
# Copiar units systemd user
# ---------------------------------------------------------------------------
echo "Copiando units systemd ..."
for service_file in assets/*.service; do
    [ -f "$service_file" ] && cp "$service_file" "${STAGING}/usr/lib/systemd/user/"
done

# ---------------------------------------------------------------------------
# Copiar .desktop
# ---------------------------------------------------------------------------
cp packaging/hefesto.desktop "${STAGING}/usr/share/applications/hefesto.desktop"

# ---------------------------------------------------------------------------
# Criar wrappers /usr/bin/
# ---------------------------------------------------------------------------
cat > "${STAGING}/usr/bin/hefesto" <<'WRAPPER'
#!/bin/sh
exec python3 -m hefesto.cli.app "$@"
WRAPPER
chmod 755 "${STAGING}/usr/bin/hefesto"

cat > "${STAGING}/usr/bin/hefesto-gui" <<'WRAPPER'
#!/bin/sh
exec python3 -m hefesto.app.main "$@"
WRAPPER
chmod 755 "${STAGING}/usr/bin/hefesto-gui"

# ---------------------------------------------------------------------------
# Copiar e ajustar arquivos DEBIAN/
# ---------------------------------------------------------------------------
echo "Preparando metadados DEBIAN/ ..."
cp packaging/debian/control "${STAGING}/DEBIAN/control"

# Injeta versao correta no control (caso difira do hardcoded)
if command -v sed >/dev/null 2>&1; then
    sed -i "s/^Version: .*/Version: ${VERSION}/" "${STAGING}/DEBIAN/control"
fi

for script in postinst prerm postrm; do
    if [ -f "packaging/debian/${script}" ]; then
        cp "packaging/debian/${script}" "${STAGING}/DEBIAN/${script}"
        chmod 755 "${STAGING}/DEBIAN/${script}"
    fi
done

# ---------------------------------------------------------------------------
# Calcular tamanho instalado (em KB, como exige o formato Debian)
# ---------------------------------------------------------------------------
INSTALLED_SIZE=$(du -sk "${STAGING}" | awk '{print $1}')
# Adiciona campo Installed-Size ao control se não existir
if ! grep -q '^Installed-Size:' "${STAGING}/DEBIAN/control"; then
    # Insere apos a linha Architecture
    sed -i "/^Architecture:/a Installed-Size: ${INSTALLED_SIZE}" "${STAGING}/DEBIAN/control"
fi

# ---------------------------------------------------------------------------
# Build do .deb
# ---------------------------------------------------------------------------
mkdir -p dist

OUTPUT_DEB="dist/hefesto_${VERSION}_amd64.deb"

echo "Construindo ${OUTPUT_DEB} ..."
dpkg-deb --build --root-owner-group "${STAGING}" "${OUTPUT_DEB}"

# ---------------------------------------------------------------------------
# Relatorio final
# ---------------------------------------------------------------------------
SIZE=$(du -sh "$OUTPUT_DEB" | awk '{print $1}')
SHA=$(sha256sum "$OUTPUT_DEB" | awk '{print $1}')

echo ""
echo "Pacote gerado com sucesso:"
echo "  Arquivo : ${OUTPUT_DEB}"
echo "  Tamanho : ${SIZE}"
echo "  SHA-256 : ${SHA}"
echo ""
echo "Para instalar localmente:"
echo "  sudo apt install ./${OUTPUT_DEB}"
echo ""
echo "Para verificar conteudo:"
echo "  dpkg-deb -c ${OUTPUT_DEB}"
