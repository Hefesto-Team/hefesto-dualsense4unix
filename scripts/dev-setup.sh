#!/usr/bin/env bash
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

echo "[dev-setup] validando PyGObject (GUI GTK3)..."
if "$VENV_DIR/bin/python" -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" >/dev/null 2>&1; then
    echo "[dev-setup] OK: PyGObject disponível no venv (GUI pronta)."
else
    cat <<'HINT'
[dev-setup] AVISO: PyGObject ausente ou incompleto no .venv.
            Gates de teste passam, mas a GUI não sobe e os
            testes da janela (exigir_gi_real) pulam em vez de rodar.
            Para habilitar GUI (opt-in):

              sudo apt install python3-gi libgirepository-1.0-dev \
                               gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
              bash scripts/dev_bootstrap.sh --with-tray

            Armadilha A-12 — ver VALIDATOR_BRIEF.md.
HINT
fi
