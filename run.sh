#!/usr/bin/env bash
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
FORCE=0
SMOKE_DURATION="${HEFESTO_DUALSENSE4UNIX_SMOKE_DURATION:-2.0}"
EXTRA=()

if [[ $# -eq 0 ]]; then
    MODE="gui"
fi

for arg in "$@"; do
    case "$arg" in
        --gui)    MODE="gui" ;;
        --tray)   MODE="tray" ;;
        --smoke)  MODE="smoke" ;;
        --daemon) MODE="daemon" ;;
        --fake)   MODE="daemon"; FAKE=1 ;;
        --bt)     TRANSPORT="bt" ;;
        --usb)    TRANSPORT="usb" ;;
        --force)  FORCE=1 ;;
        *) EXTRA+=("$arg") ;;
    esac
done

if [[ -n "${GDK_PIXBUF_MODULE_FILE:-}" && -r "${GDK_PIXBUF_MODULE_FILE}" ]]; then
    if grep -qE '^"/snap/' "${GDK_PIXBUF_MODULE_FILE}" 2>/dev/null \
       && [[ "${SNAP:-}" != /snap/* ]]; then
        unset GDK_PIXBUF_MODULE_FILE
    fi
fi

if [[ "$MODE" == "tray" ]]; then
    exec python3 -m hefesto_dualsense4unix.cli.app tray ${EXTRA[@]+"${EXTRA[@]}"}
fi

if [[ "$MODE" == "gui" ]]; then
    if [[ "${HEFESTO_DUALSENSE4UNIX_XWAYLAND:-}" == "1" ]] \
       && [[ "${GDK_BACKEND:-}" != "x11" ]]; then
        export GDK_BACKEND=x11
    fi
    exec python3 "${HERE}/scripts/abrir_interface.py" ${EXTRA[@]+"${EXTRA[@]}"}
fi

export HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT="$TRANSPORT"

if [[ "$MODE" == "smoke" ]]; then
    export HEFESTO_DUALSENSE4UNIX_FAKE=1
    export HEFESTO_DUALSENSE4UNIX_LOG_FORMAT="${HEFESTO_DUALSENSE4UNIX_LOG_FORMAT:-console}"
    export HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME="${HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME:-hefesto-dualsense4unix-smoke.sock}"
    SMOKE_LOG="/tmp/hefesto_dualsense4unix_smoke_${TRANSPORT}.log"
    echo "[smoke] iniciando daemon com FakeController transport=$TRANSPORT por ${SMOKE_DURATION}s..." | tee "$SMOKE_LOG"
    echo "[smoke] socket IPC isolado: $HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME" | tee -a "$SMOKE_LOG"
    echo "[smoke] log em: $SMOKE_LOG" | tee -a "$SMOKE_LOG"
    python3 - <<PY 2>&1 | tee -a "$SMOKE_LOG"
import asyncio
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.main import build_controller
from hefesto_dualsense4unix.utils.logging_config import configure_logging


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
    export HEFESTO_DUALSENSE4UNIX_FAKE=1
    export HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME="${HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME:-hefesto-dualsense4unix-fake.sock}"
fi

if [[ "$FAKE" != "1" ]] && [[ "$FORCE" != "1" ]] \
   && systemctl --user is-active --quiet hefesto-dualsense4unix.service 2>/dev/null; then
    echo "erro: o daemon do systemd (hefesto-dualsense4unix.service) já está ATIVO." >&2
    echo "  Subir um segundo daemon de produção aqui faria os dois disputarem o" >&2
    echo "  socket IPC (GUI/applet/CLI falando com o daemon errado). Escolha:" >&2
    echo "    systemctl --user stop hefesto-dualsense4unix.service   # pare o de produção, ou" >&2
    echo "    ./run.sh --fake                                        # daemon isolado (socket próprio), ou" >&2
    echo "    ./run.sh --daemon --force                              # forçar mesmo assim" >&2
    exit 1
fi

exec hefesto-dualsense4unix daemon start --foreground
