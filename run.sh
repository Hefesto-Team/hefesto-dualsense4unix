#!/usr/bin/env bash
# Runtime-real runner: exercita o daemon via FakeController em modos USB/BT,
# ou via pydualsense quando há hardware. Atende meta-regra 9.8 (validação
# runtime-real) para sprints que tocam o daemon.
#
# Uso:
#   ./run.sh                   abre a INTERFACE (as dez abas em HTML)
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
FORCE=0
SMOKE_DURATION="${HEFESTO_DUALSENSE4UNIX_SMOKE_DURATION:-2.0}"
# O QUE ESTE ARQUIVO NÃO ENTENDE VAI PARA A INTERFACE, e não vira aviso. Sem
# isto, `./run.sh --oculta` abria uma janela VISÍVEL na tela dela e dizia
# "argumento desconhecido" — medido em 01/09/2026, com ela usando a máquina.
EXTRA=()

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
        --force)  FORCE=1 ;;
        *) EXTRA+=("$arg") ;;
    esac
done

# Um terminal empacotado (snap/flatpak) exporta GDK_PIXBUF_MODULE_FILE
# apontando para o cache de loaders DELE. Todo processo GTK lançado daquele
# terminal herda o apontamento, e o librsvg de dentro do confinamento pede uma
# glibc mais nova que a do hospedeiro: o dlopen falha e o GTK ABORTA o processo
# no primeiro ícone que precisar de SVG — a janela morre ao abrir, com
# "Unable to load image-loading module ... GLIBC_2.xx not found".
#
# `app/main.py` também faz esta limpeza, com critério mais fino. Aqui ela cobre
# o que roda ANTES do Python subir (o smoke abaixo, entre outros), e por isso o
# critério é o grosso: se todos os módulos do cache moram dentro de /snap e nós
# não estamos lá dentro, o cache não serve para este processo.
if [[ -n "${GDK_PIXBUF_MODULE_FILE:-}" && -r "${GDK_PIXBUF_MODULE_FILE}" ]]; then
    if grep -qE '^"/snap/' "${GDK_PIXBUF_MODULE_FILE}" 2>/dev/null \
       && [[ "${SNAP:-}" != /snap/* ]]; then
        unset GDK_PIXBUF_MODULE_FILE
    fi
fi

if [[ "$MODE" == "gui" ]]; then
    # XWayland no COSMIC: popups de GtkMenu/GtkComboBox quebram no cosmic-comp
    # Wayland nativo (fundo claro, mal-posicionados, grab quebrado / "segurar
    # o clique"). ATÉ 06/09/2026 `app/main.py` também fazia isto, em Python e
    # com critério fino (conferia se havia X VIVO); ele saiu com a janela GTK
    # (`GTK-3`, `D-0609-GTK-LEVA-INTEIRA`) e a versão fina mudou de casa para
    # `app/arranque.forcar_xwayland_no_cosmic`, que HOJE NINGUÉM CHAMA. Ou seja:
    # este bloco deixou de ser a garantia grossa de um caminho e passou a ser a
    # ÚNICA cura. Fechar essa distância é trabalho de `scripts/abrir_interface.py`.
    # Aqui garante o caminho dev/launcher/.desktop antes do Python subir. A sessão COSMIC do Pop!_OS
    # exporta GDK_BACKEND=wayland,x11 (prefere wayland) — sobrescrevemos para
    # x11. Opt-out: HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND=1.
    if [[ "${HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND:-}" != "1" ]] \
       && [[ "${GDK_BACKEND:-}" != "x11" ]] \
       && [[ "${XDG_CURRENT_DESKTOP:-}${XDG_SESSION_DESKTOP:-}" == *[Cc][Oo][Ss][Mm][Ii][Cc]* ]]; then
        export GDK_BACKEND=x11
    fi
    # A INTERFACE QUE ABRE É A HTML — 01/09/2026, ordem dela: *"tudo tem que
    # apontar pro nosso lancher html e tudo tem que apontar pros arquivos na
    # nossa pasta"*, e antes disso *"a versão antiga não segue disponível, vai
    # gerar confusão nos agentes. Só a nova está disponível e deve ser
    # integrada"*.
    #
    # Aqui havia `python3 -m hefesto_dualsense4unix.app.main`, a janela GTK
    # velha — e ela era o que o `.desktop` instalado abria, porque o `install.sh`
    # aponta o `Exec=` para este arquivo. O motor não sumiu: os 74 handlers de
    # `app/actions/`, o `app/ipc_bridge.py` e as camadas de `app/telas/` são o
    # que a interface nova chama. O que mudou é o LANÇADOR.
    #
    # Passa pelo `scripts/abrir_interface.py` de propósito: é ele que veste
    # prgname, WM_CLASS e ícone no PROCESSO antes da primeira janela nascer —
    # sem isso a dock não acha o `.desktop` e o ícone sai genérico.
    # `${EXTRA[@]+…}` e não `${EXTRA[@]}`: sob `set -u`, um array VAZIO expande
    # para uma string vazia em bash 4.3 e anteriores, e a interface receberia um
    # argumento em branco. A forma com `+` não expande nada quando não há nada.
    exec python3 "${HERE}/scripts/abrir_interface.py" ${EXTRA[@]+"${EXTRA[@]}"}
fi

export HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT="$TRANSPORT"

if [[ "$MODE" == "smoke" ]]; then
    export HEFESTO_DUALSENSE4UNIX_FAKE=1
    export HEFESTO_DUALSENSE4UNIX_LOG_FORMAT="${HEFESTO_DUALSENSE4UNIX_LOG_FORMAT:-console}"
    # Isola o socket IPC do smoke para não colidir com o daemon de produção
    # (systemd). Ver docs/process/sprints/BUG-IPC-01.md e VALIDATOR_BRIEF A-03.
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
    # BUG-RUN-FAKE-HIJACK-PROD-SOCKET-01: o modo --fake usa FakeController (setters
    # no-op, sem HID/evdev). Sem isolar o socket IPC, ele bindava o socket de
    # PRODUÇÃO e, via single-instance "última vence", SEQUESTRAVA o daemon real —
    # GUI/applet/CLI passavam a falar com um daemon fake e "nada aplicava" no
    # controle (cor/gatilho/LED viravam no-op; o grab nunca acontecia). Isola o
    # socket como o --smoke já faz. Quem quiser apontar a GUI/CLI para o fake
    # precisa exportar o mesmo HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME.
    export HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME="${HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME:-hefesto-dualsense4unix-fake.sock}"
fi

# BUG-MULTI-INSTANCE-RUNSH-GUARD-01: um daemon de PRODUÇÃO aqui (socket default)
# disputaria o socket IPC com o daemon do systemd — GUI/applet/CLI passariam a
# falar com o daemon errado e "nada aplicaria" (o pepino do daemon órfão). O
# --fake é isento: tem socket E pid-lock isolados (ver run_daemon/single_instance_name).
# Override consciente com --force.
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

# "Faça o pequeno bem que está próximo." — Tolstói
