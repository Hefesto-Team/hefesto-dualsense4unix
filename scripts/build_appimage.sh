#!/usr/bin/env bash
# Gera AppImage do Hefesto - Dualsense4Unix via python-appimage (opcional).
#
# Pré-requisitos:
#   sudo apt install libfuse2 librsvg2-bin
#   pip install python-appimage build
#
# Uso:
#   ./scripts/build_appimage.sh              # Python 3.12 por padrão
#   PYTHON_VERSION=3.11 ./scripts/build_appimage.sh
#
# Saída: dist/appimage/Hefesto-Dualsense4Unix-<version>-x86_64.AppImage
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

# Verifica que o PNG canonico do icone existe. v3.4.3+ removeu o SVG
# placeholder (chama laranja); o PNG real 256x256 (martelo + gradiente)
# em assets/appimage/Hefesto-Dualsense4Unix.png e a única source canonica.
if [[ ! -f "$APPDIR_SRC/Hefesto-Dualsense4Unix.png" ]]; then
    echo "erro: PNG do icone ausente em $APPDIR_SRC/Hefesto-Dualsense4Unix.png"
    echo "       (o repo distribui o PNG real; verifique o checkout)"
    exit 3
fi

# Garante que catalogos i18n estao compilados (necessário para o wheel
# embarcar os .mo via pyproject `[tool.hatch.build.targets.wheel] include`).
# FEAT-I18N-CATALOGS-01 (v3.4.0). Idempotente — re-compila do .po.
if [[ ! -d "$HERE/src/hefesto_dualsense4unix/locale" ]] \
        || [[ -z "$(ls "$HERE/src/hefesto_dualsense4unix/locale" 2>/dev/null)" ]]; then
    echo "[i18n] catalogos .mo ausentes — compilando do po/..."
    bash "$HERE/scripts/i18n_compile.sh"
fi

# Garante que há um wheel atualizado.
if ! ls "$HERE/dist"/hefesto_dualsense4unix-*.whl >/dev/null 2>&1; then
    echo "[2/4] Nenhum wheel em dist/. Buildando..."
    python -m build --wheel
fi

# Copia appdir e aponta requirements pro wheel local (offline).
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp -r "$APPDIR_SRC/." "$WORK_DIR/"
chmod +x "$WORK_DIR/entrypoint.sh"

# OS CINCO SCRIPTS QUE O PRODUTO EXECUTA (25/08/2026, BG-04). Até aqui só o
# .deb os levava (build_deb.sh:234): quem instalava por AppImage rodava
# `doctor --fix` e recebia "não encontrado — pulado" nas três curas que ele
# delega a script (cli/cmd_doctor.py:182-186), com um único conselho de tela —
# rodar um ./install.sh que não existe na máquina de quem não clonou o
# repositório. Quem consome cada um está escrito no manifesto do Flatpak, dono
# único dessa lista.
#
# ESTE BUNDLE É CLI-ONLY (o cabeçalho do assets/appimage/entrypoint.sh diz por
# quê), então o consumidor aqui é o `hefesto-dualsense4unix doctor`, não os
# botões da janela.
#
# NÃO VERIFICADO, e é por isso que existe a conferência lá embaixo: o
# `python-appimage` monta o AppDir a partir desta pasta-receita, e eu NÃO
# consegui medir se ele copia arquivo que não seja um dos nomes especiais dele
# (entrypoint.sh, requirements.txt, .desktop, ícone) — a ferramenta não está
# nesta bancada. Em vez de escrever uma promessa que ninguém conferiu, o build
# ABRE o AppImage pronto e confere; se os cinco não estiverem lá dentro, ele
# falha nomeando o arquivo, e quem vier resolve com o meio que funcionar.
install -Dm755 -t "$WORK_DIR/usr/share/hefesto-dualsense4unix/scripts/" \
    "$HERE/scripts/doctor.sh" \
    "$HERE/scripts/bluez_config.sh" \
    "$HERE/scripts/disable_steam_input.sh" \
    "$HERE/scripts/fix_wireplumber_default_source.sh" \
    "$HERE/scripts/install_snd_quirk.sh"

WHEEL=$(ls -t "$HERE/dist"/hefesto_dualsense4unix-*.whl | head -1)
cat > "$WORK_DIR/requirements.txt" <<EOF
$WHEEL
EOF

mkdir -p "$OUT_DIR"
# Le versão do pyproject.toml (Python 3.11+ tem tomllib nativo; fallback tomli)
# Mesmo padrão de build_deb.sh — zero dependência de `import hefesto_dualsense4unix` funcionar.
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
# --name não pode ter espaços (vira posicionais separados sem aspas).
# Forma ident sem espaços; display brand "Hefesto - Dualsense4Unix" fica
# no .desktop e na janela GTK.
python-appimage build app \
    --python-version "$PYTHON_VERSION" \
    --linux-tag "manylinux2014_x86_64" \
    --name "Hefesto-Dualsense4Unix" \
    "$WORK_DIR"

# python-appimage cria no cwd com nome Hefesto-Dualsense4Unix-x86_64.AppImage
if [[ -f "$HERE/Hefesto-Dualsense4Unix-x86_64.AppImage" ]]; then
    mv "$HERE/Hefesto-Dualsense4Unix-x86_64.AppImage" "$OUT_FILE"
fi

if [[ -f "$OUT_FILE" ]]; then
    chmod +x "$OUT_FILE"

    # A CONFERÊNCIA DOS CINCO SCRIPTS, feita no bundle PRONTO e não na receita.
    # Ver o bloco "NÃO VERIFICADO" lá em cima: a pergunta é se o
    # python-appimage carregou o que pusemos em $WORK_DIR/usr/share, e a única
    # resposta honesta vem de abrir o arquivo que saiu.
    #
    # Três desfechos, e os três dizem o que são:
    #   extraiu e achou os cinco  -> segue
    #   extraiu e faltou algum    -> ERRO, nomeando o arquivo (a promessa
    #                                estaria escrita e não cumprida)
    #   não conseguiu extrair     -> AVISO, sem reprovar: aqui quem falhou foi
    #                                o instrumento, e instrumento mudo não é
    #                                prova de defeito.
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

# "A obra prova o mestre." — Sabedoria popular
