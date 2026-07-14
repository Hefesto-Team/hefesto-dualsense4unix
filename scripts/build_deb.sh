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
    "${STAGING}/usr/share/locale" \
    "${STAGING}/opt/hefesto-dualsense4unix"

# ---------------------------------------------------------------------------
# Criar venv bundlado em /opt/hefesto-dualsense4unix/venv/
# ---------------------------------------------------------------------------
VENV_DIR="${STAGING}/opt/hefesto-dualsense4unix/venv"

# Python target = o python3 DEFAULT da distro de build. O venv (--copies) linka
# contra libpython3.X.so.1.0 dessa versão exata; logo o .deb é especifico da
# versão de Python (= da distro). Por isso o CI builda UM .deb por distro
# (Jammy 22.04 -> 3.10, Noble 24.04 -> 3.12) e o filename + o Depends abaixo
# carregam a versão, para os dois coexistirem no release e o apt instalar só o
# compativel (BUG-DEB-VENV-CROSS-PYVER-01: venv 3.10 quebrava no 24.04 por
# falta de libpython3.10).
TARGET_PYTHON="/usr/bin/python3"
if [ ! -x "$TARGET_PYTHON" ]; then
    echo "Erro: /usr/bin/python3 não encontrado." >&2
    exit 1
fi
PYVER="$("$TARGET_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTAG="py$(printf '%s' "$PYVER" | tr -d .)"
echo "Python target: ${TARGET_PYTHON} ($(${TARGET_PYTHON} --version 2>&1)) -> ${PYTAG}"

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
# PACKAGING-UDEV-DEB-PARITY-01: empacota o conjunto canônico 70/71/72/76/77 —
# PARIDADE com scripts/install_udev.sh (native) e scripts/install-host-udev.sh.
# 76 (touchpad-libinput-ignore) e 77 (leds) NÃO são opt-in: sem a 76 o touchpad
# do DualSense briga com a emulação de mouse (feature-título point-and-click);
# sem a 77 a lightbar/player-LED via sysfs não grava. As 73/74 (hotplug-GUI)
# ficam de fora (alimentavam a re-enumeração do storm -71); a 75 (disable-usb-
# audio) é a genuinamente opt-in.
echo "Copiando regras udev ..."
for rules_file in assets/70-*.rules assets/71-*.rules assets/72-*.rules \
                  assets/76-*.rules assets/77-*.rules assets/78-*.rules; do
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
# Cura de raiz do storm: o usuário do .deb precisa poder consultar/reverter
# (`--status` / `--remove`) sem o repo. O script resolve o .conf em /usr/share.
install -Dm755 scripts/install_snd_quirk.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/install_snd_quirk.sh"
# Também copia o conf modules-load para o local que o helper procura
# em /usr/share/hefesto-dualsense4unix/modules-load/.
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load"
install -Dm644 assets/hefesto-dualsense4unix.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load/hefesto-dualsense4unix.conf"
# SPRINT-GAME-RUMBLE-01: a cura de RAIZ do storm (quirk do snd_usb_audio).
# DOIS destinos, de propósito:
#   1. /usr/lib/modprobe.d/ — o path VIVO que o kmod lê de verdade (junto com
#      /etc/modprobe.d). É o que faz a cura PEGAR no .deb sem passo manual; o
#      dpkg o remove no purge. (BUG-DEB-MODPROBE-INERT-PATH-01: só empacotar em
#      /usr/share deixava a cura INERTE — o kernel nunca lê de lá.)
#   2. /usr/share/.../modprobe/ — cópia espelhada que o install-host-udev.sh e o
#      install_snd_quirk.sh procuram (mesma lógica das udev-rules acima).
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    "${STAGING}/usr/lib/modprobe.d/hefesto-dualsense-storm.conf"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe"
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe/hefesto-dualsense-storm.conf"
# Idem para udev-rules (cópia espelhada — o /usr/lib/udev/rules.d/ já tem
# as regras vivas, mas o helper procura em /usr/share/.../udev-rules/).
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules"
for rules_file in assets/70-*.rules assets/71-*.rules assets/72-*.rules \
                  assets/76-*.rules assets/77-*.rules assets/78-*.rules; do
    [ -f "$rules_file" ] && install -Dm644 "$rules_file" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/$(basename "$rules_file")"
done

# ---------------------------------------------------------------------------
# Copiar catalogos i18n (.mo) — FEAT-I18N-CATALOGS-01 (v3.4.0)
# ---------------------------------------------------------------------------
# Os .mo precisam estar em /usr/share/locale/<lang>/LC_MESSAGES/<domain>.mo
# para o gettext encontrar (candidate path #3 do utils/i18n.py).
if [ -d "locale" ]; then
    echo "Copiando catalogos i18n (.mo) ..."
    for lang_dir in locale/*/; do
        [ -d "$lang_dir" ] || continue
        lang="$(basename "$lang_dir")"
        src_mo="${lang_dir}LC_MESSAGES/hefesto-dualsense4unix.mo"
        [ -f "$src_mo" ] || continue
        install -Dm644 "$src_mo" \
            "${STAGING}/usr/share/locale/${lang}/LC_MESSAGES/hefesto-dualsense4unix.mo"
    done
else
    echo "aviso: locale/ ausente — rode 'bash scripts/i18n_compile.sh' antes do build se quiser i18n"
fi

# ---------------------------------------------------------------------------
# Copiar units systemd user
# ---------------------------------------------------------------------------
echo "Copiando units systemd ..."
# PACKAGING-DEB-SERVICES-EXPLICIT-01: só as units que FUNCIONAM no contexto .deb
# (binários em /usr/bin, resolvidos pelo sed abaixo). As demais de assets/
# (storm-watch, steam-input-guard, dsx-recover) dependem de scripts que o .deb
# não instala ou de placeholders (__SCRIPT__) que só o install.sh nativo resolve
# — empacotá-las deixaria units quebradas visíveis em list-unit-files.
for base in hefesto-dualsense4unix.service hefesto-dualsense4unix-gui-hotplug.service; do
    service_file="assets/${base}"
    [ -f "$service_file" ] || continue
    cp "$service_file" "${STAGING}/usr/lib/systemd/user/${base}"
    # ExecStart no source usa %h/.local/bin/... (path do install.sh nativo
    # que cria symlink). No .deb o binário fica em /usr/bin/. O sed cobre tanto
    # o CLI quanto o -gui (o -gui casa pelo prefixo). Substituir in-place.
    sed -i 's|%h/\.local/bin/hefesto-dualsense4unix|/usr/bin/hefesto-dualsense4unix|g' \
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

# Exigir a versão EXATA do Python contra a qual o venv foi linkado. Sem isto,
# `python3 (>= 3.10)` também casa o 3.12 do Noble e o apt instalaria o .deb
# py310 num sistema sem libpython3.10 -> venv quebrado. Com `python${PYVER}`,
# o apt recusa o pacote na distro errada (o py310 não instala no 24.04, que
# não tem 3.10) e o usuário pega o .deb correto da sua distro.
sed -i "s/^Depends: /Depends: python${PYVER}, /" "${STAGING}/DEBIAN/control"

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

# Filename carrega a tag de Python (ex.: _py310 / _py312) para os .debs das
# duas distros coexistirem no mesmo release sem colisão.
OUTPUT_DEB="dist/hefesto-dualsense4unix_${VERSION}_amd64_${PYTAG}.deb"

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
