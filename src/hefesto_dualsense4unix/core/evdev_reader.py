"""Leitor de input do DualSense via evdev.

Contorna o conflito com `hid_playstation` kernel driver: quando o kernel
assume o controle como joystick (`/dev/input/event*`), `pydualsense` não
recebe reports de input — mas o próprio kernel expõe tudo via evdev.

Usado pelo `PyDualSenseController` como fonte primária de input; o
pydualsense mantém o caminho de output (`set_trigger`, `set_led`,
`set_rumble`), que continua funcionando via HID-raw.

Thread dedicada lê eventos e atualiza um snapshot protegido por RLock.
"""
from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DUALSENSE_VENDOR = 0x054C
DUALSENSE_PIDS = {0x0CE6, 0x0DF2}  # DualSense + DualSense Edge


@dataclass
class EvdevSnapshot:
    """Snapshot imutável do estado lido via evdev."""

    l2_raw: int = 0
    r2_raw: int = 0
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)


def _is_virtual_evdev(event_path: str) -> bool:
    """True se o evdev é um device VIRTUAL (uinput), não o controle físico.

    FEAT-DSX-GAMEPAD-FLAVOR-01 — CRÍTICO: o gamepad virtual com máscara DualSense
    tem o MESMO VID/PID/nome/caps do controle real, então sem este filtro o
    `find_dualsense_evdev` poderia retornar o PRÓPRIO device virtual do daemon
    (feedback loop: o daemon lendo a própria saída). Devices uinput vivem sob
    `/sys/devices/virtual/input/`; os reais, sob caminhos de USB/Bluetooth.
    """
    import os

    try:
        name = os.path.basename(event_path)  # ex.: "event12"
        link = os.path.realpath(f"/sys/class/input/{name}/device")
        return "/devices/virtual/" in link
    except Exception:
        return False


def _event_num(path: Path) -> int:
    """Número do node evdev (`event12` → 12) para ordenação determinística."""
    import re

    m = re.search(r"(\d+)$", path.name)
    return int(m.group(1)) if m else 0


class InputDirWatch:
    """Detector barato de mudança em /dev/input (PERF-MULTI-CONTROLLER-01).

    A enumeração completa (`discover_dualsense_evdevs`) abre TODOS os nodes de
    input (open + ioctls + close, ~10-40ms) — caro demais para rodar em timer
    de 2s no event loop (era o hitch rítmico do co-op). O conjunto de nodes só
    muda em hotplug/re-enumeração, e isso é observável por um `os.listdir`
    (~µs). Cada consumidor tem a SUA instância (o "mudou?" é relativo ao último
    `poll()` DESTE watch).
    """

    def __init__(self, root: str = "/dev/input") -> None:
        self._root = root
        self._last: frozenset[str] | None = None

    def poll(self) -> bool:
        """True se o conteúdo de /dev/input mudou desde o último poll (ou 1ª vez)."""
        import os

        try:
            current = frozenset(os.listdir(self._root))
        except OSError:
            current = frozenset()
        changed = current != self._last
        self._last = current
        return changed


def discover_dualsense_evdevs() -> dict[str, Path]:
    """Mapeia IDENTIDADE (MAC normalizado) -> node evdev de cada DualSense físico.

    FEAT-DSX-CONTROLLER-IDENTITY-01: a identidade universal de um controle no
    projeto é o MAC (o `uniq` do evdev == `serial_number` do hidapi, ambos
    normalizados via `norm_mac`). Nodes evdev são VOLÁTEIS (re-enumeração pós
    storm/replug muda `eventN`); a chave por MAC sobrevive. Nodes sem `uniq`
    legível (não deveria acontecer com hid_playstation) usam o próprio path
    como chave-fallback, prefixado com "path:" para nunca colidir com um MAC.

    Filtra devices virtuais (uinput, ver `_is_virtual_evdev`) e nodes sem caps
    de gamepad (touchpad/motion sensors ficam de fora).
    """
    try:
        from evdev import InputDevice, ecodes, list_devices
    except ImportError:
        return {}
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    found: dict[str, Path] = {}
    for path in sorted(list_devices(), key=lambda p: _event_num(Path(p))):
        if _is_virtual_evdev(path):
            continue
        try:
            dev = InputDevice(path)
            try:
                is_gamepad = (
                    dev.info.vendor == DUALSENSE_VENDOR
                    and dev.info.product in DUALSENSE_PIDS
                )
                # O evdev principal tem gamepad caps (BTN_GAMEPAD); o touchpad não.
                if is_gamepad:
                    buttons = dev.capabilities().get(ecodes.EV_KEY, [])
                    if ecodes.BTN_GAMEPAD in buttons or ecodes.BTN_SOUTH in buttons:
                        key = norm_mac(getattr(dev, "uniq", None)) or f"path:{path}"
                        # 1º node vence em duplicata do mesmo MAC (ordem estável
                        # por número de node) — duplicata real não deve existir.
                        found.setdefault(key, Path(path))
            finally:
                dev.close()
        except Exception:
            continue
    return found


def find_all_dualsense_evdevs() -> list[Path]:
    """Todos os evdevs principais (gamepad) de DualSense FÍSICOS, ordenados.

    Compat: wrapper de `discover_dualsense_evdevs` que descarta a identidade.
    Ordena por número do node para eleição estável entre execuções.
    """
    return sorted(discover_dualsense_evdevs().values(), key=_event_num)


def find_dualsense_evdev() -> Path | None:
    """Retorna path do evdev principal do DualSense FÍSICO; None se não houver.

    Ignora devices virtuais (uinput) — ver `_is_virtual_evdev`. É o primeiro
    (ordem determinística) de `find_all_dualsense_evdevs`.
    """
    paths = find_all_dualsense_evdevs()
    return paths[0] if paths else None


# --- 8BIT-01: inventário READ-ONLY de gamepads externos -----------------

#: Nomes de barramento (linux/input.h). Hardcoded de propósito: python-evdev
#: nem sempre reexporta as constantes `BUS_*`; os dois valores são ABI estável
#: do kernel. Barramentos fora do mapa saem como hex ("0x06" etc.) — o
#: contrato é `usb | bluetooth | outro`, nunca um chute de nome.
_BUS_NAMES: dict[int, str] = {0x03: "usb", 0x05: "bluetooth"}

#: Teto da subida no sysfs ao procurar driver/hidraw a partir do input device.
#: A hierarquia real é rasa (input/inputN -> HID -> interface -> ...); 10
#: níveis cobrem USB e Bluetooth com folga sem risco de varrer /sys inteiro.
_SYSFS_WALK_MAX_LEVELS = 10


def _bus_name(bustype: int) -> str:
    """Nome legível do barramento evdev ("usb" | "bluetooth" | "0xNN")."""
    return _BUS_NAMES.get(bustype, f"0x{bustype:02x}")


def _sysfs_driver_hidraw(device_dir: str) -> tuple[str | None, str | None]:
    """(driver, hidraw) subindo o sysfs a partir do dir do input device.

    O evdev de um gamepad vive em `.../<pai>/input/inputN`; o driver do kernel
    e o nó hidraw irmão ficam em um ANCESTRAL (o HID device para hid-nintendo/
    hid-playstation, a interface USB para o xpad — que é USB-only e nem tem
    hidraw). Sobe até `_SYSFS_WALK_MAX_LEVELS` níveis colhendo:

    - ``driver``: basename do realpath do primeiro symlink `driver` encontrado
      (o driver MAIS PRÓXIMO do device — "nintendo", "xpad", ...).
    - ``hidraw``: primeiro nó de um subdir `hidraw/` (ex.: "/dev/hidraw6").

    Tolerante a ausência por contrato (8BIT-01): qualquer campo irresolvível
    sai None — inventário read-only nunca falha por sysfs incompleto.
    """
    import os

    driver: str | None = None
    hidraw: str | None = None
    current = device_dir
    for _ in range(_SYSFS_WALK_MAX_LEVELS):
        if driver is None:
            drv_link = os.path.join(current, "driver")
            if os.path.islink(drv_link):
                with contextlib.suppress(OSError):
                    driver = os.path.basename(os.path.realpath(drv_link)) or None
        if hidraw is None:
            hidraw_dir = os.path.join(current, "hidraw")
            if os.path.isdir(hidraw_dir):
                nodes: list[str] = []
                with contextlib.suppress(OSError):
                    nodes = sorted(
                        n for n in os.listdir(hidraw_dir) if n.startswith("hidraw")
                    )
                if nodes:
                    hidraw = f"/dev/{nodes[0]}"
        if driver is not None and hidraw is not None:
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return driver, hidraw


def _external_device_sysfs(event_path: str) -> tuple[str | None, str | None]:
    """Resolve (driver, hidraw) de um node evdev via /sys/class/input.

    Mesmo ponto de partida do `_is_virtual_evdev`: o realpath de
    `/sys/class/input/<eventN>/device` cai no dir do input device físico;
    a subida fica com `_sysfs_driver_hidraw`. Falha qualquer -> (None, None).
    """
    import os

    try:
        name = os.path.basename(event_path)
        device_dir = os.path.realpath(f"/sys/class/input/{name}/device")
    except Exception:
        return None, None
    return _sysfs_driver_hidraw(device_dir)


def discover_external_gamepads() -> list[dict[str, Any]]:
    """Inventário READ-ONLY de gamepads físicos NÃO-DualSense (8BIT-01).

    Enumera os evdevs com caps de gamepad (BTN_GAMEPAD/BTN_SOUTH) SEM filtro
    de vendor — 8BitDo em modo Switch (057e:2009/hid-nintendo), X-input
    (045e:028e/xpad), qualquer marca. Exclusões, nesta ordem:

    1. Virtuais via `_is_virtual_evdev` (`/devices/virtual/`): cobre o vpad
       uhid do daemon (vive sob /devices/virtual/misc/uhid), os vpads do
       Steam Input e o teclado virtual do próprio daemon (uinput) — que, além
       de virtual, nem tem caps de gamepad.
    2. DualSense/Edge físicos (`DUALSENSE_VENDOR` + `DUALSENSE_PIDS`): são o
       domínio do caminho existente (`discover_dualsense_evdevs`); este
       inventário é SÓ dos externos — uma lista de controles com um dono só.

    Por device: name, vid/pid (hex 4 dígitos minúsculo, ex. "057e"), bus
    ("usb" | "bluetooth" | "0xNN"), uniq (MAC como o kernel reporta, ou
    None), driver do kernel (readlink no sysfs, tolerante a ausência),
    evdev_path e hidraw irmão (quando resolvível). Tudo JSON-serializável.

    Dedup como no `discover_dualsense_evdevs`: 1º node (ordem estável por
    número) vence por `uniq`; sem uniq, o path é a chave (nunca colide).

    CUSTO (lição PERF-MULTI-CONTROLLER-01): abre TODOS os nodes de /dev/input
    (open + ioctls + close, ~10-40 ms) — PROIBIDO no event loop do daemon e
    em qualquer caminho quente (`state_full`/tick). Consumidor canônico: o
    handler `controller.list` sob opt-in, via thread.
    """
    try:
        from evdev import InputDevice, ecodes, list_devices
    except ImportError:
        return []
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    found: dict[str, dict[str, Any]] = {}
    for path in sorted(list_devices(), key=lambda p: _event_num(Path(p))):
        if _is_virtual_evdev(path):
            continue
        try:
            dev = InputDevice(path)
            try:
                vendor = int(dev.info.vendor)
                product = int(dev.info.product)
                if vendor == DUALSENSE_VENDOR and product in DUALSENSE_PIDS:
                    continue
                buttons = dev.capabilities().get(ecodes.EV_KEY, [])
                if not (
                    ecodes.BTN_GAMEPAD in buttons or ecodes.BTN_SOUTH in buttons
                ):
                    continue
                uniq_raw = str(getattr(dev, "uniq", "") or "").strip()
                driver, hidraw = _external_device_sysfs(path)
                entry: dict[str, Any] = {
                    "name": str(dev.name),
                    "vid": f"{vendor:04x}",
                    "pid": f"{product:04x}",
                    "bus": _bus_name(int(dev.info.bustype)),
                    "uniq": uniq_raw or None,
                    "driver": driver,
                    "evdev_path": str(path),
                    "hidraw": hidraw,
                }
                key = norm_mac(uniq_raw) or f"path:{path}"
                found.setdefault(key, entry)
            finally:
                dev.close()
        except Exception:
            continue
    return list(found.values())


class _EvdevReconnectLoop:
    """Loop base de leitura evdev com auto-reconnect e backoff exponencial.

    Encapsula o padrão duplicado entre `EvdevReader` e `TouchpadReader`.
    Subclasses implementam hooks: `_find_device`, `_handle_event`,
    `_reset_on_disconnect`, `_log_prefix` (prefixo para log events).
    """

    _device_path: Path | None
    _stop_flag: threading.Event
    _thread: threading.Thread | None
    # InputDevice atualmente aberto pelo loop (ou None). Permite grab/ungrab
    # em runtime de fora da thread (FEAT-DSX-GAMEPAD-FLAVOR-01).
    _active_dev: Any = None
    # Watch barato de /dev/input para o is_stale (lazy; PERF-MULTI-CONTROLLER-01).
    _stale_watch: Any = None
    _THREAD_NAME: ClassVar[str] = "hefesto-evdev-base"

    def _find_device(self) -> Path | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _handle_event(self, event: Any, ecodes: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    def _reset_on_disconnect(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _reapply_grab(self, dev: Any) -> None:
        """Hook de (re)aplicação de grab ao abrir o device. No-op na base."""

    def _log_prefix(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def is_available(self) -> bool:
        return self._device_path is not None

    def refresh_device(self) -> bool:
        """Re-procura o device de input quando ainda não há um path.

        Hotplug-safe: o `__init__` chama `_find_device()` uma única vez. Se o
        daemon subiu sem o controle (offline), o path nasce `None` e jamais
        seria reavaliado — o evdev criado pelo kernel hid_playstation ao plugar
        o controle nunca era localizado. `connect()` chama isto a cada
        (re)conexão para fechar essa janela (BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01).
        """
        if self._device_path is None:
            self._device_path = self._find_device()
        return self._device_path is not None

    def is_stale(self) -> bool:
        """True se o reader está preso num node de evdev OBSOLETO.

        Caso-alvo (FEAT-DSX-EVDEV-WATCHDOG-01): após uma re-enumeração do
        controle (storm -71, replug rápido) o kernel cria um novo
        /dev/input/eventN, mas o read_loop pode seguir bloqueado no fd antigo SEM
        receber ENODEV — leitura zumbi, controle "morto" sem erro. Detectamos
        comparando o path aberto com o canônico atual do finder: se ele aponta
        agora para um node DIFERENTE (e não-None), o nosso está obsoleto.

        IDLE-SAFE: ficar parado não muda o node canônico, então isto NUNCA dispara
        por ociosidade — só por troca real de node. (O daemon ainda cruza com o
        HID: só chama o watchdog quando o controller reporta conectado.)
        """
        held = self._device_path
        if held is None:
            return False  # sem device aberto: o loop de reconexão já cobre
        # PERF-MULTI-CONTROLLER-01: o node canônico só muda se /dev/input mudou
        # — checagem por listdir (~µs) evita a enumeração completa (~10-40ms)
        # a cada tick do watchdog. 1ª chamada estabelece baseline e verifica.
        watch = getattr(self, "_stale_watch", None)
        if watch is None:
            watch = InputDirWatch()
            self._stale_watch = watch
            watch.poll()
        elif not watch.poll():
            return False
        current = self._find_device()
        if current is None:
            return False  # finder transitório/sem node: conservador, não reabre
        return current != held

    def request_reopen(self, reason: str = "watchdog") -> None:
        """Força o loop a largar o device atual e reabrir o canônico.

        Zera o path em cache (próximo ciclo re-localiza o node certo) e fecha o
        fd ativo — fechar de outra thread desbloqueia o read_loop preso, que cai
        no handler de OSError → _reset_on_disconnect + reabre. Best-effort.
        """
        logger.info(f"{self._log_prefix()}_reopen_requested", reason=reason)
        self._device_path = None
        dev = self._active_dev
        if dev is not None:
            with contextlib.suppress(Exception):
                dev.close()

    def start(self) -> bool:
        if not self.is_available():
            prefix = self._log_prefix()
            key = "evdev_reader_unavailable" if prefix == "evdev" else f"{prefix}_unavailable"
            logger.debug(key)
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, name=self._THREAD_NAME, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_flag.set()
        # M4 (auditoria): o read_loop bloqueia em select() no fd até chegar um
        # evento — com o controle OCIOSO, o `_stop_flag.is_set()` só é visto após
        # o próximo input, e o join abaixo esperava os 2s inteiros. Como o teardown
        # do co-op roda NO event loop (IPC gamepad.emulation.set), trocar a máscara
        # com P2/P3 parados congelava o input do P1 por 2-6s. Fechar o fd de outra
        # thread (idêntico a request_reopen) desbloqueia o read_loop na hora → sai
        # imediatamente. Best-effort: fd já fechado / ausente é no-op.
        dev = self._active_dev
        if dev is not None:
            with contextlib.suppress(Exception):
                dev.close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        """Loop com auto-reconnect; OSError no read_loop dispara reset + reabrir."""
        try:
            from evdev import InputDevice, ecodes
        except ImportError:
            logger.warning("evdev_module_missing")
            return

        prefix = self._log_prefix()
        backoff = 0.5
        while not self._stop_flag.is_set():
            path = self._device_path or self._find_device()
            if path is None:
                if prefix == "evdev":
                    logger.debug("evdev_device_not_found_retry", backoff=backoff)
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue
            try:
                dev = InputDevice(str(path))
            except Exception as exc:
                logger.warning(f"{prefix}_open_failed", err=str(exc), path=str(path))
                self._device_path = None
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            logger.info(f"{prefix}_started", path=str(path), name=dev.name)
            backoff = 0.5
            self._device_path = path
            self._active_dev = dev
            # Reaplica o grab se foi pedido enquanto o device estava fechado
            # (ex.: gamepad já estava ligado antes desta (re)conexão). Falha
            # NÃO é silenciosa: `_reapply_grab` registra estado + warning
            # (BUG-COOP-GRAB-SILENT-FAIL-01).
            self._reapply_grab(dev)
            try:
                for event in dev.read_loop():
                    if self._stop_flag.is_set():
                        break
                    self._handle_event(event, ecodes)
            except OSError as exc:
                if self._stop_flag.is_set():
                    # MISC-08 item 4 (2026-07-18): teardown INTENCIONAL —
                    # `stop()` fecha o fd de outra thread justamente para
                    # desbloquear este read_loop (M4), e o EBADF resultante é
                    # o mecanismo do stop, não uma perda de device. Ao vivo,
                    # cada teardown de jogador do co-op cuspia um warning
                    # `evdev_read_lost EBADF` falso-alarmante no journal.
                    logger.debug(f"{prefix}_read_stopped", path=str(path))
                else:
                    logger.warning(
                        f"{prefix}_read_lost", err=str(exc), path=str(path)
                    )
                    self._reset_on_disconnect()
                self._device_path = None
            except Exception as exc:
                logger.warning(f"{prefix}_loop_error", err=str(exc))
                self._reset_on_disconnect()
            finally:
                self._active_dev = None
                with contextlib.suppress(Exception):
                    dev.close()
            if not self._stop_flag.is_set():
                time.sleep(0.1)  # grace period antes de tentar reabrir


class EvdevReader(_EvdevReconnectLoop):
    """Lê input do DualSense via evdev em thread dedicada.

    `start()` abre o device e inicia o loop. `snapshot()` retorna o estado
    atual (thread-safe). `stop()` encerra limpo.
    """

    # Mapeamento de evdev keycode -> nome canônico no domínio Hefesto - Dualsense4Unix.
    #
    # Botões com keycode evdev estável no kernel hid_playstation:
    # cross, circle, triangle, square, l1, r1, l2_btn, r2_btn,
    # create, options, ps, l3, r3.
    #
    # Botões sem keycode evdev estável no device principal (injetados por outros caminhos):
    # - "mic_btn": vem por HID-raw via `ds.state.micBtn` (byte misc2, bit 0x04).
    #   Injetado em `PyDualSenseController.read_state()`. Ver INFRA-MIC-HID-01.
    # - dpad (up/down/left/right): vem via `_refresh_dpad_buttons` (ABS_HAT0X/Y).
    # - touchpad_*_press: device separado (name contém "Touchpad"); lido por
    #   `TouchpadReader` abaixo (INFRA-EVDEV-TOUCHPAD-01).
    BUTTON_MAP: ClassVar[dict[str, str]] = {
        "BTN_SOUTH": "cross",
        "BTN_EAST": "circle",
        "BTN_NORTH": "triangle",
        "BTN_WEST": "square",
        "BTN_TL": "l1",
        "BTN_TR": "r1",
        "BTN_TL2": "l2_btn",
        "BTN_TR2": "r2_btn",
        "BTN_SELECT": "create",
        "BTN_START": "options",
        "BTN_MODE": "ps",
        "BTN_THUMBL": "l3",
        "BTN_THUMBR": "r3",
    }

    _THREAD_NAME: ClassVar[str] = "hefesto-evdev"

    def __init__(self, device_path: Path | None = None, target_uniq: str | None = None) -> None:
        # FEAT-DSX-CONTROLLER-IDENTITY-01: quando `_target_uniq` está setado, o
        # finder resolve o node PELO MAC (identidade estável) em vez de "menor
        # node" — com 2+ controles, "menor node" e "primário do backend" podem
        # divergir após re-enumeração e o reader passaria a ler OUTRO controle.
        self._target_uniq = target_uniq
        self._device_path = device_path or self._locate()
        self._lock = threading.RLock()
        self._snapshot = EvdevSnapshot()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._dpad_x = 0
        self._dpad_y = 0
        self._pressed: set[str] = set()
        self._active_dev: Any = None
        # FEAT-DSX-GAMEPAD-FLAVOR-01: quando True, o loop faz EVIOCGRAB no
        # device — o daemon vira leitor exclusivo do controle real e os jogos
        # deixam de ver o controle cru (evitando input dobrado ao lado do
        # gamepad virtual). Aplicado/removido por `set_grab`.
        self._grab: bool = False
        # BUG-COOP-GRAB-SILENT-FAIL-01: estado observável do grab. "off" (não
        # pedido), "pending" (pedido, device ainda não aberto), "held" (ativo),
        # "failed" (EVIOCGRAB recusado — ex.: EBUSY, outro leitor já graba).
        # Falha de grab NÃO pode ser silenciosa: com gamepad virtual ligado,
        # físico sem grab = input DOBRADO no jogo.
        self._grab_state: str = "off"

    def retarget(self, uniq: str | None) -> None:
        """Re-aponta o reader para o controle de MAC `uniq` (normalizado).

        Se o node atualmente aberto não pertence ao novo alvo, força reabrir
        (fecha o fd; o loop re-localiza pelo finder, agora filtrado por MAC).
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        norm = norm_mac(uniq)
        if norm == self._target_uniq:
            return
        self._target_uniq = norm
        current = self._locate()
        if current is not None and current == self._device_path:
            return  # o node aberto já é o do alvo — nada a fazer
        self.request_reopen(reason="retarget")

    @property
    def grab_state(self) -> str:
        """Estado observável do EVIOCGRAB: off | pending | held | failed."""
        return self._grab_state

    def set_grab(self, grab: bool) -> bool:
        """Liga/desliga o EVIOCGRAB no controle físico (thread-safe-ish).

        Registra a intenção em `self._grab` (reaplicada a cada (re)conexão pelo
        loop) e tenta aplicar imediatamente no device aberto. Retorna True se o
        estado desejado foi APLICADO agora (ou é pending com device fechado —
        o loop aplica ao abrir); False se o EVIOCGRAB falhou (`grab_state` vira
        "failed" e o chamador NÃO deve assumir exclusividade do device).
        """
        self._grab = grab
        dev = self._active_dev
        if dev is None:
            self._grab_state = "pending" if grab else "off"
            return True
        # BUG-GRAB-DOUBLE-EBUSY-01: re-grabar um fd que ESTE reader já graba
        # levanta EBUSY (errno 16) no kernel — e o `except` abaixo marcava
        # `grab_state="failed"` MESMO com o device fisicamente exclusivo. Era o
        # card "grab falhou — input pode dobrar no jogo" mentindo depois de uma
        # troca de máscara/flavor (que re-chama `set_grab(True)` sem soltar antes,
        # `gamepad.py`: stop(release_grab=False) → re-grab) ou do upgrade
        # uinput→uhid. `grab_state == "held"` já significa "este fd é exclusivo":
        # nada a (re)fazer. Idempotente nos dois sentidos — ungrab de um device
        # que este reader NÃO graba ("off"/"pending"/"failed") também é no-op (o
        # `ungrab()` de um fd solto levantaria EINVAL espúrio). Um EBUSY EXTERNO
        # real (outro leitor exclusivo) nunca chega a "held" primeiro → continua
        # virando "failed" e o card segue honesto quando há duplicação de verdade.
        if grab and self._grab_state == "held":
            return True
        if not grab and self._grab_state != "held":
            self._grab_state = "off"
            return True
        try:
            if grab:
                dev.grab()
                self._grab_state = "held"
            else:
                dev.ungrab()
                self._grab_state = "off"
            return True
        except Exception as exc:
            if grab:
                self._grab_state = "failed"
                logger.warning(
                    "evdev_grab_failed",
                    path=str(self._device_path),
                    err=str(exc),
                    hint="outro leitor exclusivo? físico ficaria DOBRADO no jogo",
                )
                return False
            # ungrab falhou (device já fechado/sumiu): estado efetivo é solto.
            self._grab_state = "off"
            return True

    def snapshot(self) -> EvdevSnapshot:
        with self._lock:
            return EvdevSnapshot(
                l2_raw=self._snapshot.l2_raw,
                r2_raw=self._snapshot.r2_raw,
                lx=self._snapshot.lx,
                ly=self._snapshot.ly,
                rx=self._snapshot.rx,
                ry=self._snapshot.ry,
                buttons_pressed=self._snapshot.buttons_pressed,
            )

    # Hooks do loop base ------------------------------------------------

    def _locate(self) -> Path | None:
        """Resolve o node do controle-alvo (por MAC) ou o primeiro físico."""
        if self._target_uniq is not None:
            return discover_dualsense_evdevs().get(self._target_uniq)
        return find_dualsense_evdev()

    def _find_device(self) -> Path | None:
        return self._locate()

    def _reapply_grab(self, dev: Any) -> None:
        """Reaplica o grab pedido ao (re)abrir o device, com estado observável."""
        if not self._grab:
            return
        try:
            dev.grab()
            self._grab_state = "held"
        except Exception as exc:
            self._grab_state = "failed"
            logger.warning(
                "evdev_grab_failed",
                path=str(self._device_path),
                err=str(exc),
                hint="grab falhou ao reabrir o device; o controle pode dobrar input",
            )

    def _log_prefix(self) -> str:
        return "evdev"

    def _reset_on_disconnect(self) -> None:
        """Limpa botões 'travados' quando o device caiu."""
        with self._lock:
            self._pressed.clear()
            self._dpad_x = 0
            self._dpad_y = 0
            self._snapshot = self._with(buttons_pressed=frozenset())
        # Grab pedido volta a "pending" — será reaplicado (com verificação)
        # quando o loop reabrir o device (BUG-COOP-GRAB-SILENT-FAIL-01).
        if self._grab:
            self._grab_state = "pending"

    # Alias retrocompatível para testes legados (HOTFIX-3).
    _reset_buttons_on_disconnect = _reset_on_disconnect

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS:
            self._handle_abs(event.code, event.value, ecodes)
        elif event.type == ecodes.EV_KEY:
            self._handle_key(event.code, event.value, ecodes)

    def _handle_abs(self, code: int, value: int, ecodes: Any) -> None:
        with self._lock:
            if code == ecodes.ABS_X:
                self._snapshot = self._with(lx=value & 0xFF)
            elif code == ecodes.ABS_Y:
                self._snapshot = self._with(ly=value & 0xFF)
            elif code == ecodes.ABS_RX:
                self._snapshot = self._with(rx=value & 0xFF)
            elif code == ecodes.ABS_RY:
                self._snapshot = self._with(ry=value & 0xFF)
            elif code == ecodes.ABS_Z:
                self._snapshot = self._with(l2_raw=value & 0xFF)
            elif code == ecodes.ABS_RZ:
                self._snapshot = self._with(r2_raw=value & 0xFF)
            elif code == ecodes.ABS_HAT0X:
                self._dpad_x = int(value)
                self._refresh_dpad_buttons()
            elif code == ecodes.ABS_HAT0Y:
                self._dpad_y = int(value)
                self._refresh_dpad_buttons()

    def _handle_key(self, code: int, value: int, ecodes: Any) -> None:
        # evdev retorna keycode numerico; converte pra nome canonico
        name = self._keycode_name(code, ecodes)
        if name is None:
            return
        with self._lock:
            if value == 1:
                self._pressed.add(name)
            elif value == 0:
                self._pressed.discard(name)
            self._sync_buttons_to_snapshot()

    def _keycode_name(self, code: int, ecodes: Any) -> str | None:
        for evdev_name, hefesto_name in self.BUTTON_MAP.items():
            ev_code = getattr(ecodes, evdev_name, None)
            if ev_code is not None and ev_code == code:
                return hefesto_name
        return None

    def _refresh_dpad_buttons(self) -> None:
        for d in ("dpad_up", "dpad_down", "dpad_left", "dpad_right"):
            self._pressed.discard(d)
        if self._dpad_y < 0:
            self._pressed.add("dpad_up")
        elif self._dpad_y > 0:
            self._pressed.add("dpad_down")
        if self._dpad_x < 0:
            self._pressed.add("dpad_left")
        elif self._dpad_x > 0:
            self._pressed.add("dpad_right")
        self._sync_buttons_to_snapshot()

    def _sync_buttons_to_snapshot(self) -> None:
        self._snapshot = self._with(buttons_pressed=frozenset(self._pressed))

    def _with(self, **changes: Any) -> EvdevSnapshot:
        current = self._snapshot
        fields = ("l2_raw", "r2_raw", "lx", "ly", "rx", "ry", "buttons_pressed")
        values = {f: changes.get(f, getattr(current, f)) for f in fields}
        return EvdevSnapshot(**values)


def find_dualsense_touchpad_evdev() -> Path | None:
    """Retorna path do evdev do touchpad do DualSense; None se ausente.

    O touchpad é exposto pelo kernel `hid_playstation` como um event
    device separado do gamepad principal: mesmo vendor/product Sony
    DualSense, mas nome contendo "Touchpad" (ex: "Sony Interactive
    Entertainment DualSense Wireless Controller Touchpad").

    INFRA-EVDEV-TOUCHPAD-01 — validação empírica 2026-04-24.
    """
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        return None
    for path in list_devices():
        if _is_virtual_evdev(path):
            continue
        try:
            dev = InputDevice(path)
            try:
                if (
                    dev.info.vendor == DUALSENSE_VENDOR
                    and dev.info.product in DUALSENSE_PIDS
                    and "Touchpad" in dev.name
                ):
                    return Path(path)
            finally:
                dev.close()
        except Exception:
            continue
    return None


class TouchpadReader(_EvdevReconnectLoop):
    """Lê o touchpad do DualSense: click regionalizado + movimento do dedo.

    O touchpad emite `BTN_LEFT` (click firme mecânico, não toque leve) +
    `ABS_X` (0 a 1919) / `ABS_Y` (0 a 1079) + `BTN_TOUCH` (dedo presente) no
    device separado descoberto por `find_dualsense_touchpad_evdev`.

    Duas responsabilidades, ambas via o mesmo loop evdev:

    1. **Click regionalizado** (`regions_pressed()`): correlaciona o último
       `ABS_X` observado com o `BTN_LEFT` para discriminar três regiões —
       esquerda, meio, direita (limites 640 e 1280 sobre largura 1920). Vira
       teclas no `dispatch_keyboard`.

    2. **Movimento do cursor** (`consume_motion()`, FEAT-DSX-TOUCHPAD-CURSOR-B4):
       enquanto `BTN_TOUCH` está ativo, acumula o delta de `ABS_X`/`ABS_Y`
       entre frames. O poll loop drena esse delta a cada tick e o converte em
       REL_X/REL_Y via o mouse virtual — touchpad como fonte ÚNICA do cursor
       (a rule 76 já tira o device do libinput, então não há briga = sem
       engasgo). `BTN_TOUCH` solto zera a posição de referência: levantar e
       reapoiar o dedo em outro ponto NÃO faz o cursor pular.

    Threadsafe via RLock.
    """

    # Largura do touchpad em unidades absolutas do kernel hid_playstation
    # (empírico, DualSense USB 054c:0ce6 com kernel 6.x):
    _TOUCHPAD_WIDTH: ClassVar[int] = 1920
    # Limites de região (terços): [0, 640) esquerda; [640, 1280) meio;
    # [1280, 1920) direita.
    _REGION_LEFT_LIMIT: ClassVar[int] = 640
    _REGION_RIGHT_LIMIT: ClassVar[int] = 1280
    _THREAD_NAME: ClassVar[str] = "hefesto-touchpad"

    def __init__(self, device_path: Path | None = None) -> None:
        self._device_path = device_path or find_dualsense_touchpad_evdev()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._last_abs_x: int = self._TOUCHPAD_WIDTH // 2  # centro por default
        self._regions: frozenset[str] = frozenset()
        # Movimento do cursor (B4): dedo presente + posição de referência por
        # eixo (None = ainda sem âncora; o primeiro frame só seeda, não move) +
        # delta acumulado entre drenagens (`consume_motion`).
        self._touching: bool = False
        self._motion_last_x: int | None = None
        self._motion_last_y: int | None = None
        self._accum_dx: int = 0
        self._accum_dy: int = 0

    def regions_pressed(self) -> frozenset[str]:
        with self._lock:
            return self._regions

    def consume_motion(self) -> tuple[int, int]:
        """Retorna e zera o delta acumulado do dedo (unidades do touchpad).

        Chamado pelo poll loop a cada tick. Drena-e-reseta para que o consumo
        seja sempre o movimento desde a última chamada — o escalonamento para
        pixels (com `mouse_speed` e carry sub-pixel) é responsabilidade do
        `UinputMouseDevice.emit_touchpad_move`.
        """
        with self._lock:
            dx, dy = self._accum_dx, self._accum_dy
            self._accum_dx = 0
            self._accum_dy = 0
            return dx, dy

    @classmethod
    def _region_from_x(cls, x: int) -> str:
        if x < cls._REGION_LEFT_LIMIT:
            return "touchpad_left_press"
        if x >= cls._REGION_RIGHT_LIMIT:
            return "touchpad_right_press"
        return "touchpad_middle_press"

    # Hooks do loop base ------------------------------------------------

    def _find_device(self) -> Path | None:
        return find_dualsense_touchpad_evdev()

    def _log_prefix(self) -> str:
        return "touchpad_reader"

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_X:
                with self._lock:
                    # Snapshot de X para a região do próximo BTN_LEFT.
                    self._last_abs_x = int(event.value)
                    self._accumulate_axis_x(int(event.value))
            elif event.code == ecodes.ABS_Y:
                with self._lock:
                    self._accumulate_axis_y(int(event.value))
        elif event.type == ecodes.EV_KEY:
            if event.code == ecodes.BTN_LEFT:
                with self._lock:
                    if event.value == 1:
                        self._regions = frozenset(
                            {self._region_from_x(self._last_abs_x)}
                        )
                    elif event.value == 0:
                        self._regions = frozenset()
            elif event.code == ecodes.BTN_TOUCH:
                with self._lock:
                    # Dedo apoiado/levantado: zera a âncora dos dois eixos para
                    # que reapoiar em outro ponto não gere um salto do cursor.
                    self._touching = event.value == 1
                    self._motion_last_x = None
                    self._motion_last_y = None

    def _accumulate_axis_x(self, value: int) -> None:
        """Acumula delta de X se há dedo e âncora; senão só seeda a âncora."""
        if self._touching and self._motion_last_x is not None:
            self._accum_dx += value - self._motion_last_x
        self._motion_last_x = value

    def _accumulate_axis_y(self, value: int) -> None:
        if self._touching and self._motion_last_y is not None:
            self._accum_dy += value - self._motion_last_y
        self._motion_last_y = value

    def _reset_on_disconnect(self) -> None:
        with self._lock:
            self._regions = frozenset()
            self._touching = False
            self._motion_last_x = None
            self._motion_last_y = None
            self._accum_dx = 0
            self._accum_dy = 0


__all__ = [
    "DUALSENSE_PIDS",
    "DUALSENSE_VENDOR",
    "EvdevReader",
    "EvdevSnapshot",
    "TouchpadReader",
    "discover_external_gamepads",
    "find_all_dualsense_evdevs",
    "find_dualsense_evdev",
    "find_dualsense_touchpad_evdev",
]
