#!/usr/bin/env bash
# Runtime-real runner: exercita o daemon via FakeController em modos USB/BT,
# ou via pydualsense quando há hardware. Atende meta-regra 9.8 (validação
# runtime-real) para sprints que tocam o daemon.
#
# Uso:
#   ./run.sh                   abre a GUI GTK3 (hefesto-gui)
#   ./run.sh --gui             idem
#   ./run.sh --smoke           boot curto com FakeController USB (2s)
#   ./run.sh --smoke --bt      boot curto com FakeController BT  (2s)
#   ./run.sh --daemon          roda daemon em primeiro plano (hardware real)
#   ./run.sh --fake            igual --daemon mas usa FakeController
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [[ ! -d .venv ]]; then
    echo "erro: .venv/ não encontrado. Rode ./scripts/dev_bootstrap.sh primeiro."
    exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate

MODE="gui"
TRANSPORT="usb"
FAKE=0
SMOKE_DURATION="${HEFESTO_SMOKE_DURATION:-2.0}"

if [[ $# -eq 0 ]]; then
    MODE="gui"
fi

for arg in "$@"; do
    case "$arg" in
        --gui)    MODE="gui" ;;
        --smoke)  MODE="smoke" ;;
        --daemon) MODE="daemon" ;;
        --fake)   MODE="daemon"; FAKE=1 ;;
        --bt)     TRANSPORT="bt" ;;
        --usb)    TRANSPORT="usb" ;;
        *) echo "aviso: argumento desconhecido: $arg" ;;
    esac
done

if [[ "$MODE" == "gui" ]]; then
    exec python3 -m hefesto.app.main
fi

export HEFESTO_FAKE_TRANSPORT="$TRANSPORT"

if [[ "$MODE" == "smoke" ]]; then
    export HEFESTO_FAKE=1
    export HEFESTO_LOG_FORMAT="${HEFESTO_LOG_FORMAT:-console}"
    # Isola o socket IPC do smoke para não colidir com o daemon de produção
    # (systemd). Ver docs/process/sprints/BUG-IPC-01.md e VALIDATOR_BRIEF A-03.
    export HEFESTO_IPC_SOCKET_NAME="${HEFESTO_IPC_SOCKET_NAME:-hefesto-smoke.sock}"
    SMOKE_LOG="/tmp/hefesto_smoke_${TRANSPORT}.log"
    echo "[smoke] iniciando daemon com FakeController transport=$TRANSPORT por ${SMOKE_DURATION}s..." | tee "$SMOKE_LOG"
    echo "[smoke] socket IPC isolado: $HEFESTO_IPC_SOCKET_NAME" | tee -a "$SMOKE_LOG"
    echo "[smoke] log em: $SMOKE_LOG" | tee -a "$SMOKE_LOG"
    python3 - <<PY 2>&1 | tee -a "$SMOKE_LOG"
import asyncio
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.daemon.main import build_controller
from hefesto.utils.logging_config import configure_logging


async def main():
    configure_logging()
    daemon = Daemon(controller=build_controller(), config=DaemonConfig(poll_hz=30))
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(${SMOKE_DURATION})
    daemon.stop()
    await task
    print("[smoke] poll.tick =", daemon.store.counter("poll.tick"))
    print("[smoke] battery.change.emitted =", daemon.store.counter("battery.change.emitted"))


asyncio.run(main())
PY
    echo "[smoke] concluido." | tee -a "$SMOKE_LOG"
    exit 0
fi

if [[ "$FAKE" == "1" ]]; then
    export HEFESTO_FAKE=1
fi

exec hefesto daemon start --foreground

# "Faça o pequeno bem que está próximo." — Tolstoi
