#!/usr/bin/env bash
# Cria as 13 labels padrão do projeto via gh CLI.
# Idempotente: --force sobrescreve label existente.
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
    echo "erro: gh CLI nao encontrado. Instalar: https://cli.github.com/"
    exit 1
fi

labels=(
    "P0-critical|B60205|Bug que impede uso"
    "P1-high|D93F0B|Proxima sprint"
    "P2-medium|FBCA04|Backlog curto"
    "P3-low|0E8A16|Nice to have"
    "type:feature|1D76DB|Novo comportamento"
    "type:refactor|5319E7|Codigo muda, comportamento nao"
    "type:bug|B60205|Comportamento incorreto"
    "type:docs|0075CA|Documentacao"
    "type:infra|C5DEF5|CI, packaging, scripts"
    "type:test|BFD4F2|Testes novos"
    "status:ready|0E8A16|Disponivel pra pegar"
    "status:in-progress|FBCA04|Em execucao"
    "status:blocked|E99695|Bloqueada (comentar motivo)"
    "ai-task|7057FF|Executavel por IA autonoma"
    "needs-device|EEEEEE|Precisa DualSense fisico pra testar"
)

for entry in "${labels[@]}"; do
    IFS='|' read -r name color desc <<< "$entry"
    gh label create "$name" --color "$color" --description "$desc" --force
done

echo "OK: labels criadas/atualizadas."

# "Ordem gera paz. Paz gera pensamento. Pensamento gera obra." — Agostinho
