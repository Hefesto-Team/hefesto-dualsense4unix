#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

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

STAGING=$(mktemp -d /tmp/hefesto_deb_XXXXXX)
trap 'rm -rf "$STAGING"' EXIT

echo "Staging: ${STAGING}"

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

VENV_DIR="${STAGING}/opt/hefesto-dualsense4unix/venv"

TARGET_PYTHON="/usr/bin/python3"
if [ ! -x "$TARGET_PYTHON" ]; then
    echo "Erro: /usr/bin/python3 não encontrado." >&2
    exit 1
fi
PYVER="$("$TARGET_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTAG="py$(printf '%s' "$PYVER" | tr -d .)"
echo "Python target: ${TARGET_PYTHON} ($(${TARGET_PYTHON} --version 2>&1)) -> ${PYTAG}"

echo "Criando venv em ${VENV_DIR} ..."
"${TARGET_PYTHON}" -m venv --copies "${VENV_DIR}"

VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

echo "Atualizando pip dentro do venv ..."
"${VENV_PY}" -m pip install --quiet --upgrade pip setuptools wheel

echo "Instalando hefesto-dualsense4unix + deps no venv (off-line para o usuário final) ..."
"${VENV_PIP}" install --quiet --no-cache-dir .

echo "Adicionando shim PyGObject -> dist-packages do sistema ..."
PY_SITE_DIR=$(find "${VENV_DIR}/lib" -mindepth 1 -maxdepth 1 -type d -name 'python*' | head -1)/site-packages
mkdir -p "${PY_SITE_DIR}"
cat > "${PY_SITE_DIR}/hefesto_pygobject_shim.pth" <<'PTH'
import sys; sys.path.append('/usr/lib/python3/dist-packages')
PTH

echo "Limpando .pyc / __pycache__ / dist-info docs do venv ..."
find "${VENV_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${VENV_DIR}" -type f -name '*.pyc' -delete 2>/dev/null || true
find "${VENV_DIR}" -type d -path '*/dist-info' -name 'tests' -exec rm -rf {} + 2>/dev/null || true

FINAL_VENV="/opt/hefesto-dualsense4unix/venv"
echo "Reescrevendo shebangs do venv: ${VENV_DIR} -> ${FINAL_VENV} ..."
grep -rIl --include='*' "${VENV_DIR}/bin/python" "${VENV_DIR}/bin" 2>/dev/null \
    | xargs -r sed -i "s|${VENV_DIR}|${FINAL_VENV}|g" || true
if [ -f "${VENV_DIR}/pyvenv.cfg" ]; then
    sed -i "s|${VENV_DIR}|${FINAL_VENV}|g" "${VENV_DIR}/pyvenv.cfg" || true
fi

echo "Copiando assets/ ..."
cp -r assets/. "${STAGING}/usr/share/hefesto-dualsense4unix/assets/"; find "${STAGING}/usr/share/hefesto-dualsense4unix/assets/" -xtype l -delete

if [ -f "assets/appimage/Hefesto-Dualsense4Unix.png" ]; then
    cp "assets/appimage/Hefesto-Dualsense4Unix.png" "${STAGING}/usr/share/icons/hicolor/256x256/apps/hefesto.png"
    cp "assets/appimage/Hefesto-Dualsense4Unix.png" "${STAGING}/usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png"
fi

if [ -f "assets/simbolico/hefesto-dualsense4unix-symbolic.svg" ]; then
    mkdir -p "${STAGING}/usr/share/icons/hicolor/symbolic/apps"
    cp "assets/simbolico/hefesto-dualsense4unix-symbolic.svg" \
        "${STAGING}/usr/share/icons/hicolor/symbolic/apps/hefesto-dualsense4unix-symbolic.svg"
fi

echo "Copiando regras udev ..."
UDEV_RULES_GLOBS=(
    assets/71-*.rules assets/72-*.rules assets/73-hefesto-ps5-controller.rules
    assets/76-*.rules assets/77-*.rules assets/78-*.rules
    assets/79-*.rules assets/80-*.rules assets/81-*.rules
    assets/82-*.rules assets/83-*.rules assets/84-*.rules assets/85-*.rules
)
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    [ -f "$rules_file" ] && cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"
done

echo "Copiando helper install-host-udev.sh ..."
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/scripts"
install -Dm755 scripts/install-host-udev.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh"
install -Dm755 scripts/regra_do_no_aberta.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/regra_do_no_aberta.sh"
install -Dm755 scripts/install_snd_quirk.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/install_snd_quirk.sh"
install -Dm755 scripts/bt_nosniff_now.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_nosniff_now.sh"
install -Dm755 scripts/bt_active_mode.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_active_mode.sh"
install -Dm755 scripts/bt_ponte_privilegiada.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_ponte_privilegiada.sh"
install -Dm755 scripts/bt_bonds_autorestore.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_bonds_autorestore.sh"
install -Dm755 scripts/bt_health_watchdog.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_health_watchdog.sh"
install -Dm755 scripts/wifi_usb.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/wifi_usb.sh"
install -Dm755 scripts/bt_rebind_orphans.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_rebind_orphans.sh"
install -Dm755 scripts/bt_bonds_snapshot.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/bt_bonds_snapshot.sh"
for _s in doctor.sh bluez_config.sh disable_steam_input.sh fix_wireplumber_default_source.sh; do
    [ -f "scripts/${_s}" ] && install -Dm755 "scripts/${_s}" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/${_s}"
done
install -Dm755 scripts/o_basico.py "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/o_basico.py"
install -Dm755 scripts/identidade_do_vpad.py "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/identidade_do_vpad.py"
install -Dm755 scripts/ensaios/a_entrada_que_nasce_sozinha.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/a_entrada_que_nasce_sozinha.py"
install -Dm755 scripts/ensaios/audio_por_transporte.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/audio_por_transporte.py"
install -Dm755 scripts/ensaios/comum.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/comum.py"
install -Dm755 scripts/ensaios/entrada_em_repouso.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/entrada_em_repouso.py"
install -Dm755 scripts/ensaios/escrita_pelo_broker.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/escrita_pelo_broker.py"
install -Dm755 scripts/ensaios/giro_e_buraco.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/giro_e_buraco.py"
install -Dm755 scripts/ensaios/imu_no_cabo.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/imu_no_cabo.py"
install -Dm755 scripts/ensaios/microfone_no_cabo.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/microfone_no_cabo.py"
install -Dm755 scripts/ensaios/o_caminho_do_mic_no_cabo.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/o_caminho_do_mic_no_cabo.py"
install -Dm755 scripts/ensaios/o_jogo_para_de_ver_o_giro.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/o_jogo_para_de_ver_o_giro.py"
install -Dm755 scripts/ensaios/os_endpoints_de_haptica.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/os_endpoints_de_haptica.py"
install -Dm755 scripts/ensaios/os_nos_de_som_por_controle.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/os_nos_de_som_por_controle.py"
install -Dm755 scripts/ensaios/quem_e_quem.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/quem_e_quem.py"
install -Dm755 scripts/ensaios/taxa_no_hidraw.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/ensaios/taxa_no_hidraw.py"
install -Dm644 scripts/sondas/nucleo-por-processo.bt \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/sondas/nucleo-por-processo.bt"
install -Dm644 scripts/sondas/trava-por-pad.bt \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/sondas/trava-por-pad.bt"
install -Dm644 scripts/sondas/uhid-raw-request.bt \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/sondas/uhid-raw-request.bt"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load"
install -Dm644 assets/hefesto-dualsense4unix.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modules-load/hefesto-dualsense4unix.conf"
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    "${STAGING}/usr/lib/modprobe.d/hefesto-dualsense-storm.conf"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe"
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe/hefesto-dualsense-storm.conf"
install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf \
    "${STAGING}/usr/lib/modprobe.d/hefesto-btusb-no-autosuspend.conf"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe.d"
install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe.d/hefesto-btusb-no-autosuspend.conf"
install -Dm644 assets/modprobe.d/hefesto-hid-nintendo.conf \
    "${STAGING}/usr/lib/modprobe.d/hefesto-hid-nintendo.conf"
install -Dm644 assets/modprobe.d/hefesto-hid-nintendo.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe.d/hefesto-hid-nintendo.conf"
install -Dm644 assets/modprobe.d/hefesto-hid-playstation.conf \
    "${STAGING}/usr/lib/modprobe.d/hefesto-hid-playstation.conf"
install -Dm644 assets/modprobe.d/hefesto-hid-playstation.conf \
    "${STAGING}/usr/share/hefesto-dualsense4unix/modprobe.d/hefesto-hid-playstation.conf"
echo "Copiando fontes DKMS do hid-nintendo patchado (Onda T) ..."
install -Dm644 scripts/dkms_lib.sh \
    "${STAGING}/usr/share/hefesto-dualsense4unix/scripts/dkms_lib.sh"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/hid-nintendo"
cp -a assets/dkms/hid-nintendo/. \
    "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/hid-nintendo/"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/hid-playstation"
cp -a assets/dkms/hid-playstation/. \
    "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/hid-playstation/"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/usb-f-hid"
cp -a assets/dkms/usb-f-hid/. \
    "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/usb-f-hid/"
echo "Copiando fontes DKMS do rtw88-usb patchado (Onda W) ..."
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/rtw88-usb"
cp -a assets/dkms/rtw88-usb/. \
    "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/rtw88-usb/"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/LICENSES"
cp -a LICENSES/. \
    "${STAGING}/usr/share/hefesto-dualsense4unix/dkms/LICENSES/"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules"
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    [ -f "$rules_file" ] && install -Dm644 "$rules_file" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/$(basename "$rules_file")"
done
echo "Copiando broker root hide-hidraw (hefesto-hidraw-broker) ..."
install -Dm755 src/hefesto_dualsense4unix/broker/hidraw_broker.py \
    "${STAGING}/usr/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
bash scripts/broker_do_pacote.sh "${STAGING}/usr/lib/systemd/system" \
    /usr/lib/hefesto-dualsense4unix/hefesto-hidraw-broker
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/broker"
install -Dm644 src/hefesto_dualsense4unix/broker/hidraw_broker.py \
    "${STAGING}/usr/share/hefesto-dualsense4unix/broker/hidraw_broker.py"
mkdir -p "${STAGING}/usr/share/hefesto-dualsense4unix/systemd"
for _unit in hefesto-hidraw-broker.service hefesto-hidraw-broker.socket \
             hefesto-bt-bonds-snapshot.service; do
    [ -f "assets/systemd/${_unit}" ] && install -Dm644 "assets/systemd/${_unit}" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/systemd/${_unit}"
done
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

echo "Copiando units systemd ..."
python3 src/hefesto_dualsense4unix/utils/units_de_usuario.py \
    --assets assets --out "${STAGING}/usr/lib/systemd/user" \
    --bin-dir /usr/bin --python "${FINAL_VENV}/bin/python" > /dev/null

cp packaging/hefesto-dualsense4unix.desktop "${STAGING}/usr/share/applications/hefesto-dualsense4unix.desktop"

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

echo "Preparando metadados DEBIAN/ ..."
cp packaging/debian/control "${STAGING}/DEBIAN/control"

DEB_EPOCH="$(sed -n 's/^X-Hefesto-Deb-Epoch:[[:space:]]*//p' \
    "${STAGING}/DEBIAN/control" | head -1)"
if [ -z "${DEB_EPOCH}" ]; then
    echo "Erro: packaging/debian/control sem X-Hefesto-Deb-Epoch." >&2
    echo "      Sem epoch o apt RECUSA o upgrade de qualquer 3.x/4.0 instalado" >&2
    echo "      (0.3.0 é downgrade). Declare o epoch no control." >&2
    exit 1
fi
sed -i "/^X-Hefesto-Deb-Epoch:/d" "${STAGING}/DEBIAN/control"

if command -v sed >/dev/null 2>&1; then
    sed -i "s/^Version: .*/Version: ${DEB_EPOCH}:${VERSION}/" \
        "${STAGING}/DEBIAN/control"
fi

sed -i "s/^Depends: /Depends: python${PYVER}, /" "${STAGING}/DEBIAN/control"

for script in postinst prerm postrm; do
    if [ -f "packaging/debian/${script}" ]; then
        cp "packaging/debian/${script}" "${STAGING}/DEBIAN/${script}"
        chmod 755 "${STAGING}/DEBIAN/${script}"
    fi
done

INSTALLED_SIZE=$(du -sk "${STAGING}" | awk '{print $1}')
if ! grep -q '^Installed-Size:' "${STAGING}/DEBIAN/control"; then
    sed -i "/^Architecture:/a Installed-Size: ${INSTALLED_SIZE}" "${STAGING}/DEBIAN/control"
fi

mkdir -p dist

OUTPUT_DEB="dist/hefesto-dualsense4unix_${VERSION}_amd64_${PYTAG}.deb"

echo "Construindo ${OUTPUT_DEB} ..."
dpkg-deb --build --root-owner-group "${STAGING}" "${OUTPUT_DEB}"

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
echo "Broker root hide-hidraw (BROKER-01) — o postinst o liga sozinho."
echo "Módulos DKMS (precisam de dkms e dos headers do kernel) — depois do apt install:"
echo "  sudo /usr/share/hefesto-dualsense4unix/scripts/install-host-udev.sh"
echo ""
echo "Para verificar conteúdo:"
echo "  dpkg-deb -c ${OUTPUT_DEB}"
