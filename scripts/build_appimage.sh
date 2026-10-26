#!/usr/bin/env bash
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

if [[ ! -f "$APPDIR_SRC/Hefesto-Dualsense4Unix.png" ]]; then
    echo "erro: PNG do icone ausente em $APPDIR_SRC/Hefesto-Dualsense4Unix.png"
    echo "       (o repo distribui o PNG real; verifique o checkout)"
    exit 3
fi

if [[ ! -d "$HERE/src/hefesto_dualsense4unix/locale" ]] \
        || [[ -z "$(ls "$HERE/src/hefesto_dualsense4unix/locale" 2>/dev/null)" ]]; then
    echo "[i18n] catalogos .mo ausentes — compilando do po/..."
    bash "$HERE/scripts/i18n_compile.sh"
fi

if ! ls "$HERE/dist"/hefesto_dualsense4unix-*.whl >/dev/null 2>&1; then
    echo "[2/4] Nenhum wheel em dist/. Buildando..."
    python -m build --wheel
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp -r "$APPDIR_SRC/." "$WORK_DIR/"
chmod +x "$WORK_DIR/entrypoint.sh"

install -Dm755 -t "$WORK_DIR/usr/share/hefesto-dualsense4unix/scripts/" \
    "$HERE/scripts/doctor.sh" \
    "$HERE/scripts/bluez_config.sh" \
    "$HERE/scripts/disable_steam_input.sh" \
    "$HERE/scripts/fix_wireplumber_default_source.sh" \
    "$HERE/scripts/install_snd_quirk.sh"

install -Dm755 -t "$WORK_DIR/usr/share/hefesto-dualsense4unix/scripts/" \
    "$HERE/scripts/o_basico.py" \
    "$HERE/scripts/identidade_do_vpad.py"
install -Dm755 -t "$WORK_DIR/usr/share/hefesto-dualsense4unix/scripts/ensaios/" \
    "$HERE/scripts/ensaios/a_entrada_que_nasce_sozinha.py" \
    "$HERE/scripts/ensaios/audio_por_transporte.py" \
    "$HERE/scripts/ensaios/comum.py" \
    "$HERE/scripts/ensaios/entrada_em_repouso.py" \
    "$HERE/scripts/ensaios/escrita_pelo_broker.py" \
    "$HERE/scripts/ensaios/giro_e_buraco.py" \
    "$HERE/scripts/ensaios/imu_no_cabo.py" \
    "$HERE/scripts/ensaios/microfone_no_cabo.py" \
    "$HERE/scripts/ensaios/o_caminho_do_mic_no_cabo.py" \
    "$HERE/scripts/ensaios/o_jogo_para_de_ver_o_giro.py" \
    "$HERE/scripts/ensaios/os_endpoints_de_haptica.py" \
    "$HERE/scripts/ensaios/os_nos_de_som_por_controle.py" \
    "$HERE/scripts/ensaios/quem_e_quem.py" \
    "$HERE/scripts/ensaios/taxa_no_hidraw.py"
install -Dm644 -t "$WORK_DIR/usr/share/hefesto-dualsense4unix/scripts/sondas/" \
    "$HERE/scripts/sondas/nucleo-por-processo.bt" \
    "$HERE/scripts/sondas/trava-por-pad.bt" \
    "$HERE/scripts/sondas/uhid-raw-request.bt"

WHEEL=$(ls -t "$HERE/dist"/hefesto_dualsense4unix-*.whl | head -1)
cat > "$WORK_DIR/requirements.txt" <<EOF
$WHEEL
EOF

mkdir -p "$OUT_DIR"
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
OUT_FILE="$OUT_DIR/Hefesto-Dualsense4Unix-${VERSION}-x86_64.AppImage"
echo "Versão detectada: ${VERSION}"

echo "[3/4] Gerando AppImage com Python ${PYTHON_VERSION}..."
python-appimage build app \
    --python-version "$PYTHON_VERSION" \
    --linux-tag "manylinux2014_x86_64" \
    --name "Hefesto-Dualsense4Unix" \
    "$WORK_DIR"

if [[ -f "$HERE/Hefesto-Dualsense4Unix-x86_64.AppImage" ]]; then
    mv "$HERE/Hefesto-Dualsense4Unix-x86_64.AppImage" "$OUT_FILE"
fi

if [[ -f "$OUT_FILE" ]]; then
    chmod +x "$OUT_FILE"

    _prod_dir="usr/share/hefesto-dualsense4unix/scripts"
    _prod_tmp="$(mktemp -d)"
    if ( cd "$_prod_tmp" && "$OUT_FILE" --appimage-extract "$_prod_dir/*" ) \
            >/dev/null 2>&1; then
        _prod_faltam=()
        for _prod in doctor.sh bluez_config.sh disable_steam_input.sh \
                     fix_wireplumber_default_source.sh install_snd_quirk.sh; do
            [[ -f "$_prod_tmp/squashfs-root/$_prod_dir/$_prod" ]] \
                || _prod_faltam+=("$_prod")
        done
        if [[ "${#_prod_faltam[@]}" -gt 0 ]]; then
            echo "erro: o AppImage NÃO leva ${#_prod_faltam[@]} script(s) do produto:" >&2
            printf '       %s\n' "${_prod_faltam[@]}" >&2
            echo "       Eles foram postos em $WORK_DIR/$_prod_dir e não" >&2
            echo "       chegaram ao bundle — o python-appimage descartou a pasta." >&2
            echo "       Sem eles, 'doctor --fix' responde 'não encontrado — pulado'" >&2
            echo "       nas três curas que ele delega a script." >&2
            rm -rf "$_prod_tmp"
            exit 5
        fi
        echo "[ok] os cinco scripts do produto viajam em $_prod_dir"
    else
        echo "aviso: não consegui abrir o AppImage para conferir os cinco scripts" >&2
        echo "       do produto (--appimage-extract falhou). NÃO é prova de que" >&2
        echo "       faltam — é prova de que não medi." >&2
    fi
    rm -rf "$_prod_tmp"

    echo "[4/4] AppImage pronto:"
    ls -lh "$OUT_FILE"
    echo ""
    echo "Teste: $OUT_FILE version"
else
    echo "aviso: arquivo final não encontrado; veja logs do python-appimage."
    exit 4
fi
