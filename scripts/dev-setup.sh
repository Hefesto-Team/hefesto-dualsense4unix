#!/usr/bin/env bash
# dev-setup.sh — verificação idempotente do ambiente de dev.
#
# Uso: ./scripts/dev-setup.sh [--with-tray]
#
# Comportamento:
#   1. Se .venv/ não existe ou .venv/bin/pytest está ausente/quebrado,
#      invoca scripts/dev_bootstrap.sh para (re)criar o ambiente.
#   2. Sempre termina rodando `.venv/bin/pytest --collect-only` como smoke
#      que confirma que hefesto é importável e a suite está visível.
#   3. Reporta "Collected N tests" e sai com código 0 se tudo ok.
#
# Operacionaliza lição L-21-4: executor em sessão nova precisa do ambiente
# vivo antes de rodar qualquer gate. Execução cega é violação.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"
PYTEST_BIN="$VENV_DIR/bin/pytest"
BOOTSTRAP="$REPO_ROOT/scripts/dev_bootstrap.sh"

needs_bootstrap=0
if [[ ! -d "$VENV_DIR" ]]; then
    echo "[dev-setup] .venv/ ausente, invocando dev_bootstrap.sh..."
    needs_bootstrap=1
elif [[ ! -x "$PYTEST_BIN" ]]; then
    echo "[dev-setup] .venv/bin/pytest ausente, reinstalando..."
    needs_bootstrap=1
elif ! "$PYTEST_BIN" --version >/dev/null 2>&1; then
    echo "[dev-setup] .venv/bin/pytest quebrado, reinstalando..."
    needs_bootstrap=1
fi

if [[ "$needs_bootstrap" -eq 1 ]]; then
    bash "$BOOTSTRAP" "$@"
else
    echo "[dev-setup] .venv/ viva; pulando bootstrap."
fi

echo "[dev-setup] validando suite com pytest --collect-only..."
collected=$("$PYTEST_BIN" --collect-only -q 2>&1 | tail -5)
echo "$collected"

count=$(echo "$collected" | grep -oE '[0-9]+ tests? collected' | head -1 || true)
if [[ -z "$count" ]]; then
    echo "[dev-setup] ERRO: pytest --collect-only não retornou contagem reconhecível."
    exit 1
fi
echo "[dev-setup] OK: $count."

# "Ama a sabedoria com perseverança, e ela te elevará." — Provérbios 4:8
