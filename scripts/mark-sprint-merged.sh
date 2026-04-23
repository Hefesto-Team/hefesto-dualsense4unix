#!/usr/bin/env bash
# mark-sprint-merged.sh — Automação de atualização de status no SPRINT_ORDER.md.
#
# Uso:
#   ./scripts/mark-sprint-merged.sh <SPRINT-ID> [STATUS]
#
# Exemplos:
#   ./scripts/mark-sprint-merged.sh BUG-PLAYER-LEDS-APPLY-01
#   ./scripts/mark-sprint-merged.sh CHORE-CI-REPUBLISH-TAGS-01 PROTOCOL_READY
#   ./scripts/mark-sprint-merged.sh HARDEN-IPC-RUMBLE-CUSTOM-01 SUPERSEDED
#
# STATUS válidos: MERGED (default), PROTOCOL_READY, SUPERSEDED, IN_PROGRESS.
#
# O script:
#   1. Valida que o ID existe no SPRINT_ORDER.md.
#   2. Faz sed cirúrgico substituindo PENDING → <STATUS> (ou IN_PROGRESS se
#      estiver em andamento).
#   3. NÃO commita — deixa working tree pronto para o commit da sprint em si.
#
# Se STATUS=MERGED e o sprint toca .md + commita em sprint separada ou junto,
# o fluxo canônico é:
#
#   # ... aplicar fixes da sprint ...
#   ./scripts/mark-sprint-merged.sh <SPRINT-ID>
#   git add -A
#   git commit -m "tipo: SPRINT-ID breve descrição"
#   git push origin main
set -euo pipefail

ID="${1:-}"
STATUS="${2:-MERGED}"

if [[ -z "$ID" ]]; then
    echo "erro: forneça SPRINT-ID como primeiro argumento."
    echo "uso: $0 <SPRINT-ID> [STATUS]"
    exit 1
fi

case "$STATUS" in
    PENDING|IN_PROGRESS|MERGED|PROTOCOL_READY|SUPERSEDED) ;;
    *)
        echo "erro: STATUS inválido '$STATUS'."
        echo "válidos: PENDING IN_PROGRESS MERGED PROTOCOL_READY SUPERSEDED"
        exit 1
        ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORDER_FILE="$REPO_ROOT/docs/process/SPRINT_ORDER.md"

if [[ ! -f "$ORDER_FILE" ]]; then
    echo "erro: $ORDER_FILE não encontrado."
    exit 1
fi

# Localizar linha do sprint
if ! grep -q "\*\*${ID}\*\*" "$ORDER_FILE"; then
    echo "erro: sprint \"${ID}\" não encontrado em SPRINT_ORDER.md."
    echo "Verifique se o ID está cercado por **...** na tabela."
    exit 1
fi

# sed: só altera última coluna (status) da linha que contém **ID** — pattern
# robusto: troca o que vier após o último `|` da linha alvo por `${STATUS}`.
# Compatível com BSD sed (macOS) e GNU sed.
tmpfile=$(mktemp)
awk -v id="$ID" -v new="$STATUS" '
{
    if (index($0, "**" id "**") > 0 && index($0, "|") > 0) {
        # Tabelas markdown terminam em "|", então split gera campo vazio no
        # fim. Substitui o penúltimo (parts[n-1]) que é a última célula real.
        n = split($0, parts, "|")
        target_idx = (parts[n] == "" || parts[n] ~ /^[[:space:]]*$/) ? n-1 : n
        if (target_idx >= 2) {
            parts[target_idx] = " " new " "
            line = parts[1]
            for (i=2; i<=n; i++) line = line "|" parts[i]
            print line
        } else {
            print $0
        }
    } else {
        print $0
    }
}
' "$ORDER_FILE" > "$tmpfile"
mv "$tmpfile" "$ORDER_FILE"

echo "[mark-sprint-merged] ${ID} → ${STATUS}"
echo "Diff aplicado em: $ORDER_FILE"
echo "Próximos passos:"
echo "  git diff docs/process/SPRINT_ORDER.md"
echo "  git add -A && git commit -m '<tipo>: ${ID} <descrição>'"

# "Faça o pequeno bem que está próximo." — Tolstói
