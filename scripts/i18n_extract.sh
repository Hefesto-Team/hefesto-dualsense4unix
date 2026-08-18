#!/usr/bin/env bash
# i18n_extract.sh — Extrai strings traduzíveis do código Python e do
# Glade gerando po/hefesto-dualsense4unix.pot.
#
# FEAT-I18N-CATALOGS-01 (v3.4.0). Idempotente — re-rodar sobrescreve
# .pot e dá merge automático nos .po existentes preservando traduções.
#
# Requer: gettext (xgettext, msgmerge). No Ubuntu: `sudo apt install
# gettext`.
#
# Uso:
#   bash scripts/i18n_extract.sh             # extrai + merge en/pt_BR
#   bash scripts/i18n_extract.sh --add fr_FR # adiciona idioma novo
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

DOMAIN="hefesto-dualsense4unix"
POT="po/${DOMAIN}.pot"
PYTHON_SRC="src/hefesto_dualsense4unix"
GLADE="src/hefesto_dualsense4unix/gui/main.glade"

if ! command -v xgettext >/dev/null 2>&1; then
    echo "ERRO: xgettext ausente. Instale: sudo apt install gettext" >&2
    exit 1
fi

mkdir -p po locale

# Extrai strings Python (todas as ocorrências de `_()`).
# --add-comments=TRANSLATORS captura comentários `# TRANSLATORS: ...`
# acima das strings para dar contexto aos tradutores.
echo "[1/3] extraindo strings Python..."
find "$PYTHON_SRC" -type f -name "*.py" \
    -not -path "*/tests/*" \
    -not -path "*/__pycache__/*" \
    -print0 \
    | xargs -0 xgettext \
        --language=Python \
        --keyword=_ \
        --keyword=N_ \
        --from-code=UTF-8 \
        --add-comments=TRANSLATORS \
        --copyright-holder="Hefesto - Dualsense4Unix project" \
        --package-name="$DOMAIN" \
        --package-version="3.4.0" \
        --msgid-bugs-address="[REDACTED]" \
        --output="$POT.python"

# Extrai strings do Glade (todos os attributes translatable="yes").
# `xgettext --language=Glade` é nativo no gettext 0.20+.
echo "[2/3] extraindo strings do Glade..."
xgettext \
    --language=Glade \
    --from-code=UTF-8 \
    --output="$POT.glade" \
    "$GLADE"

# Concatena Python + Glade num único .pot.
echo "[3/3] fundindo catálogos em $POT..."
msgcat --use-first --output-file="$POT" "$POT.python" "$POT.glade"
rm -f "$POT.python" "$POT.glade"

# Atualiza .po existentes preservando traduções (merge inteligente).
for po in po/*.po; do
    [[ -f "$po" ]] || continue
    lang="$(basename "$po" .po)"
    echo "  merging $lang..."
    msgmerge --update --backup=none --quiet "$po" "$POT"
done

# Suporta criação de novo idioma via --add LANG.
if [[ "${1:-}" == "--add" ]] && [[ -n "${2:-}" ]]; then
    new_lang="$2"
    new_po="po/${new_lang}.po"
    if [[ -f "$new_po" ]]; then
        echo "aviso: $new_po já existe; pulando criação"
    else
        echo "  criando po/${new_lang}.po a partir do .pot..."
        msginit --no-translator --locale="$new_lang" \
            --input="$POT" --output-file="$new_po"
    fi
fi

echo ""
echo "Extração concluída: $POT"
echo "Idiomas presentes: $(ls po/*.po 2>/dev/null | xargs -n1 basename | sed 's/.po//' | tr '\n' ' ')"
echo ""
echo "Próximo passo: bash scripts/i18n_compile.sh"
