#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

DOMAIN="hefesto-dualsense4unix"
POT="po/${DOMAIN}.pot"
PYTHON_SRC="src/hefesto_dualsense4unix"
GLADE="src/hefesto_dualsense4unix/gui/main.glade"

SEM_A_JANELA=0
if [[ "${1:-}" == "--sem-a-janela" ]]; then
    SEM_A_JANELA=1
    shift
fi

if ! command -v xgettext >/dev/null 2>&1; then
    echo "ERRO: xgettext ausente. Instale: sudo apt install gettext" >&2
    exit 1
fi

trap 'rm -f "$POT.python" "$POT.glade"' EXIT

if [[ ! -f "$GLADE" ]] && [[ "$SEM_A_JANELA" -eq 0 ]]; then
    cat >&2 <<FIM
ERRO: $GLADE não existe, e ele era a fonte de 317 das 413 frases deste catálogo.

A janela GTK FOI APOSENTADA em 06/09/2026 (D-0609-GTK-LEVA-INTEIRA:
o registro «GTK-3-os-sessenta-e-dois-testes-e-a-remocao» de 06/09/2026)
e o arquivo não volta. Este rc=1 é permanente e é de propósito: quem gerar o
catálogo daqui em diante decide, POR ESCRITO, aceitar um catálogo 72% menor.
As frases da interface NOVA moram em src/hefesto_dualsense4unix/interface/
(páginas HTML e os geradores abaNN.py) e NENHUM extrator as alcança hoje — o
passo [1/3] só pega \`_()\` e \`N_()\` em Python.

ESTE SCRIPT NÃO SEGUE SOZINHO porque seguir custaria tradução: o msgmerge
comentaria as ~299 frases ausentes em cada po/*.po, e o produto não tem hoje
de onde repô-las.

  para gerar o catálogo só do Python, de propósito e por escrito:
      bash scripts/i18n_extract.sh --sem-a-janela

  para o catálogo inteiro voltar: dar um extrator às páginas da interface nova.
FIM
    exit 1
fi

mkdir -p po locale

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
        --copyright-holder="Hefesto - DualSense4Unix project" \
        --package-name="$DOMAIN" \
        --package-version="3.4.0" \
        --msgid-bugs-address="[REDACTED]" \
        --output="$POT.python"

if [[ -f "$GLADE" ]]; then
    echo "[2/3] extraindo strings do Glade..."
    xgettext \
        --language=Glade \
        --from-code=UTF-8 \
        --output="$POT.glade" \
        "$GLADE"
else
    echo "[2/3] SEM A JANELA: $GLADE não existe e --sem-a-janela foi pedido."
    echo "      O catálogo sai só com as frases do Python; as da janela GTK"
    echo "      (317 na última medição) ficam de fora, e as da interface nova"
    echo "      continuam sem extrator."
    : > "$POT.glade"
fi

echo "[3/3] fundindo catálogos em $POT..."
msgcat --use-first --output-file="$POT" "$POT.python" "$POT.glade"
rm -f "$POT.python" "$POT.glade"

for po in po/*.po; do
    [[ -f "$po" ]] || continue
    lang="$(basename "$po" .po)"
    echo "  merging $lang..."
    msgmerge --update --backup=none --quiet "$po" "$POT"
done

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
