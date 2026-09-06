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
#   bash scripts/i18n_extract.sh                 # extrai + merge en/pt_BR
#   bash scripts/i18n_extract.sh --add fr_FR     # adiciona idioma novo
#   bash scripts/i18n_extract.sh --sem-a-janela  # aceita o catálogo SEM o glade
#
# A JANELA GTK ESTÁ SENDO APOSENTADA (D-0609-GTK-LEVA-INTEIRA), e ela é 77%
# deste catálogo. MEDIDO em 06/09/2026, na sprint GTK-2:
#
#   com o glade      413 msgid  ·  317 referências apontam para o XML da janela
#   só do Python     114 msgid
#
# O QUE ESTE SCRIPT FAZIA QUANDO O GLADE SUMIA — medido, não suposto: o
# `xgettext` do passo [2/3] devolvia rc≠0, o `set -e` matava o script ali, e o
# estrago era em DOIS lugares calados. Primeiro, `po/*.pot` ficava com o
# conteúdo ANTIGO — o catálogo continuava publicando as 317 frases de uma
# janela que já não existe, e nada dizia isso. Segundo, o `rm -f` do passo
# [3/3] nunca rodava, e `po/*.pot.python` (17 KB) ficava para trás no `po/`.
# A única coisa que se via era um "failed to load external entity" do gettext,
# que não nomeia nem a causa nem a decisão.
#
# AGORA O SCRIPT DECIDE ANTES DE COMEÇAR, e nunca extrai menos calado:
# ou o glade está lá e o catálogo é o de sempre, ou ele PARA dizendo o que
# sumiu e quanto custa — e quem quiser o catálogo menor pede por escrito, com
# `--sem-a-janela`, e ouve quantas frases ficaram de fora.
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

# OS PARCIAIS SAEM DE QUALQUER JEITO. Sem isto, uma parada no meio deixa
# `po/*.pot.python` no `po/` — e foi exatamente o que a medição de 06/09 achou.
trap 'rm -f "$POT.python" "$POT.glade"' EXIT

# A FONTE DA JANELA: ou ela está aí, ou este script PARA e diz o que sumiu.
if [[ ! -f "$GLADE" ]] && [[ "$SEM_A_JANELA" -eq 0 ]]; then
    cat >&2 <<FIM
ERRO: $GLADE não existe, e ele era a fonte de 317 das 413 frases deste catálogo.

A janela GTK FOI APOSENTADA em 06/09/2026 (D-0609-GTK-LEVA-INTEIRA:
docs/process/sprints/2026-09-06-GTK-3-os-sessenta-e-dois-testes-e-a-remocao.md)
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
if [[ -f "$GLADE" ]]; then
    echo "[2/3] extraindo strings do Glade..."
    xgettext \
        --language=Glade \
        --from-code=UTF-8 \
        --output="$POT.glade" \
        "$GLADE"
else
    # Só se chega aqui com `--sem-a-janela`: a guarda do topo já parou quem não
    # pediu. E ele DIZ o tamanho do buraco, em vez de fundir um catálogo menor
    # como se nada tivesse mudado.
    echo "[2/3] SEM A JANELA: $GLADE não existe e --sem-a-janela foi pedido."
    echo "      O catálogo sai só com as frases do Python; as da janela GTK"
    echo "      (317 na última medição) ficam de fora, e as da interface nova"
    echo "      continuam sem extrator."
    : > "$POT.glade"
fi

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
