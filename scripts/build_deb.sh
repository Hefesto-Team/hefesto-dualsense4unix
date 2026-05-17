#!/usr/bin/env bash
# build_deb.sh — Gera pacote .deb para o Hefesto - Dualsense4Unix com venv bundlado.
#
# BUG-DEB-DEPS-VENV-BUNDLED-01: a estratégia anterior dependia de pacotes
# python3-* do apt que em Ubuntu 22.04 (Jammy) entregam versões antigas
# (pydantic 1.x, structlog 20.1, typer 0.3) e não tem `python3-pydualsense`.
# Resultado: `apt install` aceitava o .deb mas `hefesto-dualsense4unix --help`
# falhava por incompatibilidade. Solução: criar um venv pinado em
# `/opt/hefesto-dualsense4unix/venv/` com pip dentro do build, bundlar no
# .deb. Wrappers `/usr/bin/` apontam para o python desse venv. PyGObject
# (python3-gi) continua sendo herdado do sistema via --system-site-packages
# porque é caro recompilar com pip.
#
# Uso: bash scripts/build_deb.sh
# Saida: dist/hefesto-dualsense4unix_<version>_amd64.deb

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Le versão do pyproject.toml (Python 3.11+ tem tomllib nativo; fallback tomli)
# ---------------------------------------------------------------------------
VERSION=$(python3 - <<'EOF'
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit("Erro: tomllib (Python 3.11+) ou tomli não encontrado. Instale: pip install tomli")
with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
print(data["project"]["version"])
EOF
)

echo "Versão detectada: ${VERSION}"

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
    "${STAGING}/usr/lib/udev/rules.d" \
    "${STAGING}/usr/lib/systemd/user" \
    "${STAGING}/usr/share/applications" \
    "${STAGING}/usr/share/hefesto-dualsense4unix/assets" \
    "${STAGING}/usr/share/icons/hicolor/256x256/apps" \
    "${STAGING}/opt/hefesto-dualsense4unix"

# ---------------------------------------------------------------------------
# Criar venv bundlado em /opt/hefesto-dualsense4unix/venv/
# ---------------------------------------------------------------------------
VENV_DIR="${STAGING}/opt/hefesto-dualsense4unix/venv"

# Pegar Python target compatível com Ubuntu/Pop! >= 22.04. python3.10 é a
# versão padrão do Jammy (libpython3.10.so.1.0 vem com python3-minimal).
# `python3` default em distros newer pode ser 3.11/3.12 — venv ficaria
# embarcando libpython mais nova que Jammy não tem (BUG diagnosticado em
# build local com Pop!_OS 22.04 + pyenv 3.12 → libpython3.12.so missing
# em ubuntu:22.04). Preferir 3.10 via fallback explícito.
TARGET_PYTHON=""
for cand in /usr/bin/python3.10 /usr/bin/python3.11 /usr/bin/python3.12 /usr/bin/python3; do
    if [ -x "$cand" ]; then
        TARGET_PYTHON="$cand"
        break
    fi
done
if [ -z "$TARGET_PYTHON" ]; then
    echo "Erro: nenhum Python 3 do sistema (/usr/bin/python3*) encontrado." >&2
    exit 1
fi
echo "Python target: ${TARGET_PYTHON} ($(${TARGET_PYTHON} --version 2>&1))"

echo "Criando venv em ${VENV_DIR} ..."
# --copies (não symlink — venv autocontido sobrevive entre máquinas).
# NÃO usar --system-site-packages aqui: durante o build, o host pode ter
# python3-typer/python3-pydantic/etc. instalados e o pip "veria" como
# satisfeitas, pulando-as do venv. No target Jammy puro, faltariam.
# PyGObject (gi) é resolvido depois via .pth (abaixo).
"${TARGET_PYTHON}" -m venv --copies "${VENV_DIR}"

VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

echo "Atualizando pip dentro do venv ..."
"${VENV_PY}" -m pip install --quiet --upgrade pip setuptools wheel

echo "Instalando hefesto-dualsense4unix + deps no venv (off-line para o usuário final) ..."
"${VENV_PIP}" install --quiet --no-cache-dir .

# PyGObject é resolvido a partir de python3-gi do sistema (apt). Compilá-lo
# via pip exige libgirepository-1.0-dev e cairo, o que infla muito o build.
# Em vez disso, adicionar um .pth que injeta /usr/lib/python3/dist-packages
# no sys.path do venv quando ele é executado. python3-gi do apt do target
# (Jammy ou superior) coloca os módulos `gi`, `gi/repository`, `cairo` lá.
echo "Adicionando shim PyGObject -> dist-packages do sistema ..."
PY_SITE_DIR=$(find "${VENV_DIR}/lib" -mindepth 1 -maxdepth 1 -type d -name 'python*' | head -1)/site-packages
mkdir -p "${PY_SITE_DIR}"
cat > "${PY_SITE_DIR}/hefesto_pygobject_shim.pth" <<'PTH'
import sys; sys.path.append('/usr/lib/python3/dist-packages')
PTH

# Limpeza pós-install — encolher o venv removendo arquivos que não rodam.
echo "Limpando .pyc / __pycache__ / dist-info docs do venv ..."
find "${VENV_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${VENV_DIR}" -type f -name '*.pyc' -delete 2>/dev/null || true
find "${VENV_DIR}" -type d -path '*/dist-info' -name 'tests' -exec rm -rf {} + 2>/dev/null || true

# Reescrever shebangs para apontar para o caminho FINAL (/opt/...) — durante
# a criação o venv embarcou shebangs com o path do staging.
FINAL_VENV="/opt/hefesto-dualsense4unix/venv"
echo "Reescrevendo shebangs do venv: ${VENV_DIR} -> ${FINAL_VENV} ..."
grep -rIl --include='*' "${VENV_DIR}/bin/python" "${VENV_DIR}/bin" 2>/dev/null \
    | xargs -r sed -i "s|${VENV_DIR}|${FINAL_VENV}|g" || true
# Patch também o pyvenv.cfg — armazena o home original do interpretador.
if [ -f "${VENV_DIR}/pyvenv.cfg" ]; then
    sed -i "s|${VENV_DIR}|${FINAL_VENV}|g" "${VENV_DIR}/pyvenv.cfg" || true
fi

# ---------------------------------------------------------------------------
# Copiar assets
# ---------------------------------------------------------------------------
echo "Copiando assets/ ..."
cp -r assets/. "${STAGING}/usr/share/hefesto-dualsense4unix/assets/"

# Icone principal (usa o da pasta appimage que é o mais completo)
if [ -f "assets/appimage/Hefesto-Dualsense4Unix.png" ]; then
    cp "assets/appimage/Hefesto-Dualsense4Unix.png" "${STAGING}/usr/share/icons/hicolor/256x256/apps/hefesto.png"
fi

# ---------------------------------------------------------------------------
# Copiar regras udev
# ---------------------------------------------------------------------------
echo "Copiando regras udev ..."
for rules_file in assets/70-*.rules assets/71-*.rules assets/72-*.rules assets/73-*.rules assets/74-*.rules; do
    [ -f "$rules_file" ] && cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"
done

# v3.3.1: bundla install-host-udev.sh em /usr/share para re-aplicar regras
# manualmente fora do apt install (ex: usuário renomeou /etc/udev/rules.d/
# por engano, ou quer re-trigger após upgrade do kernel). O script resolve
# origem em 3 contextos (Flatpak /app/share, .deb /usr/share, source
# ../assets) — aqui só o .deb precisa do helper exposto.
echo "Copiando helper install-host-udev.sh ..."
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/scripts"
install -Dm755 scripts/install-host-udev.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh"
# Também copia o conf modules-load para o local que o helper procura
# em /usr/share/hefesto-dualsense4unix/modules-load/.
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load"
install -Dm644 assets/hefesto-dualsense4unix.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load/hefesto-dualsense4unix.conf"
# Idem para udev-rules (cópia espelhada — o /usr/lib/udev/rules.d/ já tem
# as regras vivas, mas o helper procura em /usr/share/.../udev-rules/).
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules"
for rules_file in assets/70-*.rules assets/71-*.rules assets/72-*.rules assets/73-*.rules assets/74-*.rules; do
    [ -f "$rules_file" ] && install -Dm644 "$rules_file" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/$(basename "$rules_file")"
done

# ---------------------------------------------------------------------------
# Copiar units systemd user
# ---------------------------------------------------------------------------
echo "Copiando units systemd ..."
for service_file in assets/*.service; do
    [ -f "$service_file" ] || continue
    base=$(basename "$service_file")
    cp "$service_file" "${STAGING}/usr/lib/systemd/user/${base}"
    # ExecStart no source usa %h/.local/bin/... (path do install.sh nativo
    # que cria symlink). No .deb o binário fica em /usr/bin/. Substituir
    # in-place pra unit apontar pro wrapper correto.
    sed -i 's|%h/\.local/bin/hefesto-dualsense4unix|/usr/bin/hefesto-dualsense4unix|g' \
        "${STAGING}/usr/lib/systemd/user/${base}"
    sed -i 's|%h/\.local/bin/hefesto-dualsense4unix-gui|/usr/bin/hefesto-dualsense4unix-gui|g' \
        "${STAGING}/usr/lib/systemd/user/${base}"
done

# ---------------------------------------------------------------------------
# Copiar .desktop
# ---------------------------------------------------------------------------
cp packaging/hefesto-dualsense4unix.desktop "${STAGING}/usr/share/applications/hefesto-dualsense4unix.desktop"

# ---------------------------------------------------------------------------
# Criar wrappers /usr/bin/ apontando para o venv bundlado
# ---------------------------------------------------------------------------
# O venv carrega todas as deps Python pinadas no build; PyGObject vem do
# sistema (python3-gi) via --system-site-packages do venv. Os wrappers
# usam o python do venv explicitamente.
cat > "${STAGING}/usr/bin/hefesto-dualsense4unix" <<WRAPPER
#!/bin/sh
exec ${FINAL_VENV}/bin/hefesto-dualsense4unix "\$@"
WRAPPER
chmod 755 "${STAGING}/usr/bin/hefesto-dualsense4unix"

cat > "${STAGING}/usr/bin/hefesto-dualsense4unix-gui" <<WRAPPER
#!/bin/sh
exec ${FINAL_VENV}/bin/hefesto-dualsense4unix-gui "\$@"
WRAPPER
chmod 755 "${STAGING}/usr/bin/hefesto-dualsense4unix-gui"

# ---------------------------------------------------------------------------
# Copiar e ajustar arquivos DEBIAN/
# ---------------------------------------------------------------------------
echo "Preparando metadados DEBIAN/ ..."
cp packaging/debian/control "${STAGING}/DEBIAN/control"

# Injeta versão correta no control (caso difira do hardcoded)
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

OUTPUT_DEB="dist/hefesto-dualsense4unix_${VERSION}_amd64.deb"

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
echo "Para verificar conteúdo:"
echo "  dpkg-deb -c ${OUTPUT_DEB}"
