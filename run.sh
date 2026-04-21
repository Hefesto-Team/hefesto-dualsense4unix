#!/usr/bin/env bash
# Runtime-real runner: exercita o daemon via FakeController em modos USB/BT,
# ou via pydualsense quando há hardware. Atende meta-regra 9.8 (validação
# runtime-real) para sprints que tocam o daemon.
#
# Uso:
#   ./run.sh --smoke           boot curto com FakeController USB (2s)
#   ./run.sh --smoke --bt      boot curto com FakeController BT  (2s)
#   ./run.sh --daemon          roda daemon em primeiro plano (hardware real)
#   ./run.sh --fake            igual --daemon mas usa FakeController
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [[ ! -d .venv ]]; then
    echo "erro: .venv/ nao encontrado. Rode ./scripts/dev_bootstrap.sh primeiro."
    exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate

MODE="daemon"
TRANSPORT="usb"
FAKE=0
SMOKE_DURATION="${HEFESTO_SMOKE_DURATION:-2.0}"

for arg in "$@"; do
    case "$arg" in
        --smoke)  MODE="smoke" ;;
        --daemon) MODE="daemon" ;;
        --fake)   MODE="daemon"; FAKE=1 ;;
        --bt)     TRANSPORT="bt" ;;
        --usb)    TRANSPORT="usb" ;;
        *) echo "aviso: argumento desconhecido: $arg" ;;
    esac
done

export HEFESTO_FAKE_TRANSPORT="$TRANSPORT"

if [[ "$MODE" == "smoke" ]]; then
    export HEFESTO_FAKE=1
    export HEFESTO_LOG_FORMAT="${HEFESTO_LOG_FORMAT:-console}"
    echo "[smoke] iniciando daemon com FakeController transport=$TRANSPORT por ${SMOKE_DURATION}s..."
    python3 - <<PY
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
    echo "[smoke] concluido."
    exit 0
fi

if [[ "$FAKE" == "1" ]]; then
    export HEFESTO_FAKE=1
fi

exec hefesto daemon start --foreground

# "Faca o pequeno bem que esta proximo." — Tolstoi
