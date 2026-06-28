"""Backend real usando `pydualsense` para falar HID com o DualSense.

Thin adapter: traduz chamadas da `IController` para a API do pydualsense e
converte estado interno em `ControllerState` imutável. Mantém intencionalmente
sem lógica de negócio — facilita troca do backend no futuro (ADR-001).

FEAT-DSX-MULTI-CONTROLLER-01: suporta N DualSense conectados ao mesmo tempo.
A `pydualsense` NÃO é multi-device nativamente — `pydualsense.__find_device`
(`# TODO: implement multiple controllers working`) abre o controle por VID/PID
e fica com "o último enumerado". Para abrir cada controle de forma
determinística, usamos uma subclasse (`_PinnedPyDualSense`) que sobrescreve o
`__find_device` manglado e abre por `path` (hidraw) via `hidapi.Device`. Assim:

  - OUTPUT (gatilhos, lightbar, rumble, LEDs de player, LED do mic) é aplicado
    a TODOS os controles (fan-out) e o "perfil ativo" é cacheado em `_desired`
    para ser re-aplicado a um controle plugado em runtime (hotplug-in).
  - INPUT/EMULAÇÃO permanece SÓ no controle PRIMÁRIO (o evdev e o `read_state`
    seguem single-instance; o `_ds` aponta para o primário). 100% compatível
    com o caso de 1 controle.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydualsense import pydualsense

from hefesto_dualsense4unix.core.controller import (
    ControllerState,
    IController,
    Side,
    Transport,
    TriggerEffect,
)
from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    EvdevReader,
)

if TYPE_CHECKING:
    from collections.abc import Callable

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: PID do DualSense Edge (os demais PIDs em `DUALSENSE_PIDS` são o DualSense
#: comum). Usado para sinalizar `is_edge` ao abrir o handle.
DUALSENSE_EDGE_PID = 0x0DF2

#: Timeout para `pydualsense.init()` em segundos
#: (BUG-BACKEND-PYDUALSENSE-DSTATE-01). A chamada faz HID I/O sync via libhidapi
#: e, em certos estados degenerados do USB (driver kernel hid_playstation
#: contendendo o device, hidraw com handle órfão de daemon anterior, hub em
#: low-power-state), pode entrar em `D (disk sleep)` no kernel — nem SIGKILL
#: mata. Envolvemos em thread + futures com timeout: se passar do prazo, o
#: backend é marcado como offline-OK e a próxima tentativa do reconnect_loop
#: cobre. A thread em D-state é abandonada (vaza recurso, mas o daemon segue
#: vivo e funcional). 5s é compromisso entre cobrir o caso patológico e não
#: pesar no boot normal (`init()` saudável retorna em <300ms).
INIT_TIMEOUT_SEC: float = float(os.environ.get("HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC", "5"))

#: Throttle do report_thread da pydualsense (segundos de sleep por ciclo
#: read+write). O loop `sendReport` do upstream roda SEM pausa, na taxa do
#: controle (~250Hz-1kHz), martelando o hidraw. Com 2+ controles são 2+ threads
#: saturando o controlador USB compartilhado — e o adaptador Bluetooth vive no
#: MESMO controlador (família do storm), degradando o link BT
#: (`DualSense input CRC's check failed`) e matando o output do controle BT.
#: Como o INPUT vem do evdev (não do `read` da pydualsense), dá pra throttlar o
#: ciclo sem perder responsividade: ~125Hz de output é de sobra para
#: gatilhos/LED/rumble, e a leitura de bateria/transporte é esparsa.
#: BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01.
REPORT_THREAD_THROTTLE_SEC: float = float(
    os.environ.get("HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC", "0.008")
)


@dataclass
class _DesiredOutput:
    """Último output aplicado = "perfil ativo" materializado em HID.

    Re-aplicado a cada handle recém-aberto (hotplug-in), garantindo que um
    controle plugado em runtime receba o mesmo perfil dos demais. O rumble é
    transitório (efeito de jogo, não faz parte de um perfil) e por isso NÃO
    entra aqui — não seria correto "ressuscitar" um rumble antigo num controle
    novo.
    """

    trigger_left: TriggerEffect | None = None
    trigger_right: TriggerEffect | None = None
    led: tuple[int, int, int] | None = None
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None
    mic_led: bool | None = None


class _PinnedPyDualSense(pydualsense):  # type: ignore[misc]
    """`pydualsense` "pinada" a um hidraw `path` específico (multi-controle).

    Sobrescreve o `__find_device` manglado do upstream (que abre por VID/PID e
    fica com "o último enumerado") para abrir DETERMINISTICAMENTE o device do
    `path` informado via `hidapi.Device(path=...)`. É o que permite manter N
    instâncias, cada uma falando com um controle distinto.
    """

    def __init__(self, path: bytes, *, is_edge: bool) -> None:
        super().__init__()
        self._pinned_path = path
        self._pinned_is_edge = is_edge

    # O nome manglado de `pydualsense.__find_device` é
    # `_pydualsense__find_device`; o `init()` do upstream chama
    # `self.__find_device()` que resolve para este override.
    def _pydualsense__find_device(self) -> tuple[Any, bool]:  # nome manglado do upstream
        import hidapi

        return hidapi.Device(path=self._pinned_path), self._pinned_is_edge

    def sendReport(self) -> None:  # noqa: N802 - override do nome do upstream
        """Igual ao loop do upstream, mas com throttle por ciclo.

        O upstream faz `read`+`write` num laço apertado sem pausa, na taxa do
        controle. Com múltiplos controles isso satura o controlador USB e
        degrada o link Bluetooth (CRC fails → output do BT morre). Como o INPUT
        real vem do evdev, aqui só precisamos do flush de OUTPUT e da leitura
        esparsa de bateria/transporte — então pausamos `REPORT_THREAD_THROTTLE_SEC`
        por ciclo. BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01.
        """
        while self.ds_thread:
            try:
                in_report = self.device.read(self.input_report_length)
                self.readInput(in_report)
                self.writeReport(self.prepareReport())
                if REPORT_THREAD_THROTTLE_SEC > 0:
                    time.sleep(REPORT_THREAD_THROTTLE_SEC)
            except OSError:
                self.connected = False
                break
            except AttributeError:
                self.connected = False
                break


class PyDualSenseController(IController):
    """Implementação de `IController` baseada em `pydualsense` (multi-controle).

    OUTPUT é aplicado a todos os controles (fan-out); INPUT/EMULAÇÃO vem só do
    controle primário. Ver o cabeçalho do módulo (FEAT-DSX-MULTI-CONTROLLER-01).
    """

    def __init__(self, evdev_reader: EvdevReader | None = None) -> None:
        # chave (serial/MAC ou path) -> handle aberto. O `dict` preserva ordem
        # de inserção (py3.7+): o 1º inserido que ainda estiver presente é o
        # PRIMÁRIO. Controles novos entram no FIM, então nunca roubam o primário
        # de um já conectado.
        self._handles: dict[str, pydualsense] = {}
        self._primary_key: str | None = None
        self._transport: Transport = "usb"
        # BUG-DAEMON-NO-DEVICE-FATAL-01: estado "offline-OK". Marcado quando não
        # há nenhum DualSense — daemon segue vivo, IPC/UDP/CLI funcionais, e
        # `connect()` é retentado periodicamente pelo `reconnect_loop`.
        self._offline: bool = False
        # Perfil ativo materializado em HID; re-aplicado no hotplug-in.
        self._desired = _DesiredOutput()
        # FEAT-DSX-CONTROLLER-SELECTOR-01: ALVO das ações de output. None =
        # TODOS (broadcast, padrão e idêntico ao histórico). Guardamos a KEY
        # estável (serial/MAC) do controle escolhido — NÃO o índice — para
        # sobreviver a hotplug/troca de porta. Se a key alvo sumir (controle
        # desconectou), o `_for_each` cai de volta em broadcast.
        self._output_target_key: str | None = None
        # Protege a mutação de `_handles`/`_primary_key` contra o fan-out de
        # escrita: o daemon roda `connect`/`read_state`/setters em executor
        # multi-thread (max_workers=2). RLock pois um caminho pode reentrar.
        self._io_lock = threading.RLock()
        # HOTFIX-2: evdev como fonte primária de input (contorna conflito
        # com kernel hid_playstation). pydualsense segue como caminho de
        # output (triggers, LED, rumble). Single-instance, atrelado ao primário.
        self._evdev = evdev_reader if evdev_reader is not None else EvdevReader()

    # --- compat: `_ds` == handle primário -------------------------------

    @property
    def _ds(self) -> pydualsense | None:
        """Handle do controle PRIMÁRIO (ou None se nenhum conectado).

        Seam de compatibilidade: todo o caminho de INPUT (`read_state`,
        `get_battery`, `is_connected` legado, `_detect_transport`) e os testes
        legados continuam falando com um único handle via este atributo.
        """
        key = self._primary_key
        return self._handles.get(key) if key is not None else None

    @_ds.setter
    def _ds(self, value: pydualsense | None) -> None:
        # Seam de compat p/ testes/legado que atribuem o handle primário direto
        # (`inst._ds = fake` / `inst._ds = None`).
        with self._io_lock:
            if value is None:
                self._handles.clear()
                self._primary_key = None
            else:
                self._handles = {"_primary": value}
                self._primary_key = "_primary"

    # --- enumeração + abertura ------------------------------------------

    @staticmethod
    def _enumerate_device_keys() -> list[tuple[str, bytes, bool]]:
        """Retorna `[(key, path, is_edge)]` de TODOS os DualSense plugados.

        `key` é a identidade PERSISTENTE do controle: o `serial_number`
        (== MAC, estável entre replug/troca de porta) quando disponível, com
        fallback para o `path` (estável por porta) quando o firmware não expõe
        serial em USB. Faz dedupe por device (uma mesma controladora pode
        enumerar múltiplas interfaces HID).

        SEAM de teste: stubável para `[]` (offline) ou uma lista fixa.
        """
        import hidapi

        out: list[tuple[str, bytes, bool]] = []
        seen: set[str] = set()
        for info in hidapi.enumerate(vendor_id=DUALSENSE_VENDOR):
            if info.product_id not in DUALSENSE_PIDS:
                continue
            # hidapi: serial_number vem de wchar_t* → str (ou None); path vem de
            # char* → bytes. NÃO chamar .decode() no serial (já é str).
            serial = info.serial_number
            key = serial if serial else info.path.decode("utf-8", "replace")
            if key in seen:  # dedupe de múltiplas interfaces do mesmo device
                continue
            seen.add(key)
            out.append((key, info.path, info.product_id == DUALSENSE_EDGE_PID))
        return out

    def _open_one(self, path: bytes, *, is_edge: bool) -> pydualsense | None:
        """Abre UM controle por `path`, com a guarda de timeout do init.

        Retorna o handle aberto, ou None se o device sumiu entre o enumerate e
        o open ("No device detected") ou se o `init()` estourou o timeout
        (BUG-BACKEND-PYDUALSENSE-DSTATE-01). Demais exceções (permissão hidraw,
        USB transitório) propagam para o chamador fazer backoff.
        """
        ds = _PinnedPyDualSense(path, is_edge=is_edge)
        # Roda `ds.init()` numa thread daemon com timeout. Se a chamada entrar
        # em D-state (kernel HID bloqueado, hidraw órfão, hub em low-power), o
        # daemon principal não trava: a thread é abandonada (daemon=True → morre
        # com o processo) e devolvemos None. O probe periódico retenta. Não
        # usamos ThreadPoolExecutor porque seu __exit__ join-aria a thread morta.
        result: list[Exception | None] = []

        def _runner() -> None:
            try:
                ds.init()
                result.append(None)
            except Exception as exc:  # propagamos para o caller via result
                result.append(exc)

        t = threading.Thread(target=_runner, daemon=True, name="hefesto-ds-init")
        t.start()
        t.join(timeout=INIT_TIMEOUT_SEC)
        if t.is_alive():
            logger.warning(
                "pydualsense_init_timeout — kernel pode estar bloqueado em "
                "hidraw (hid_playstation conflict)",
                path=path,
                timeout_sec=INIT_TIMEOUT_SEC,
            )
            return None
        exc = result[0] if result else None
        if exc is not None:
            # `pydualsense.__find_device()` levanta `Exception("No device
            # detected")` (string match — não é subclasse dedicada). Aqui isso
            # significa corrida com unplug entre enumerate e open: trata como
            # ausência (None). Demais exceções propagam.
            if "No device detected" in str(exc):
                return None
            raise exc
        return ds

    # --- ciclo de vida / reconciliação (hotplug) ------------------------

    def connect(self) -> None:
        """Reconcilia os handles abertos com os controles fisicamente plugados.

        Idempotente e usado como TICK DE HOTPLUG pelo `reconnect_loop`:
          - controle novo → abre o handle e re-aplica o PERFIL ATIVO nele;
          - controle removido → fecha o handle (sem vazar) e promove o próximo
            mais antigo a primário se for o caso;
          - já presente → mantém intacto (não reabre).
        """
        want = self._enumerate_device_keys()
        if not want:
            with self._io_lock:
                self._close_handles(keep=set())
                self._recompute_primary()
                self._offline = True
            return

        want_keys = {key for key, _, _ in want}
        with self._io_lock:
            # hotplug-OUT: fecha tudo que sumiu (sem vazar handle/thread).
            self._close_handles(keep=want_keys)
            existing = set(self._handles)

        # hotplug-IN: abre os que faltam (fora do lock — `_open_one` pode levar
        # até INIT_TIMEOUT_SEC e não deve bloquear read_state/fan-out).
        for key, path, is_edge in want:
            if key in existing:
                continue
            handle = self._open_one(path, is_edge=is_edge)
            if handle is None:
                continue  # timeout / sumiu na corrida — retenta no próximo probe
            dup: pydualsense | None = None
            with self._io_lock:
                if key in self._handles:
                    # outro probe concorrente abriu primeiro — descarta o dup.
                    dup = handle
                else:
                    self._handles[key] = handle
            if dup is not None:
                with contextlib.suppress(Exception):
                    dup.close()
                continue
            # re-aplica o perfil ativo no controle recém-chegado.
            self._reapply_desired(handle)

        with self._io_lock:
            self._recompute_primary()
            self._offline = not self._handles

    def _close_handles(self, keep: set[str]) -> None:
        """Fecha (e remove) os handles cujas chaves não estão em `keep`.

        `handle.close()` para o report_thread e fecha o `hidapi.Device` — sem
        vazar thread/handle. Chamado sob `_io_lock`.
        """
        for key in [k for k in self._handles if k not in keep]:
            handle = self._handles.pop(key)
            with contextlib.suppress(Exception):
                handle.close()
        if self._primary_key is not None and self._primary_key not in self._handles:
            self._primary_key = None

    def _recompute_primary(self) -> None:
        """(Re)elege o primário e re-atrela evdev/transport SÓ quando ele muda.

        Primário = 1ª chave de inserção ainda presente (`next(iter(...))`).
        Controles novos entram no fim, então nunca roubam o primário de um já
        conectado; se o primário cai, promove o próximo mais antigo. Chamado sob
        `_io_lock`.
        """
        prev = self._primary_key
        if self._primary_key is None or self._primary_key not in self._handles:
            self._primary_key = next(iter(self._handles), None)
        if self._primary_key is None or self._primary_key == prev:
            return
        # Trocou o primário: re-detecta transport e re-atrela o evdev a ele.
        self._transport = self._detect_transport(self._handles[self._primary_key])
        # BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01: o EvdevReader cacheia o path no
        # __init__. Se o daemon bootou offline (sem controle), o path ficava
        # None e o hotplug nunca o reavaliava — input caía no HID-raw cru
        # (sticks ~253 em repouso). Re-procura aqui, a cada troca de primário.
        self._evdev.refresh_device()
        if self._evdev.is_available():
            self._evdev.start()
            logger.info("controller_primary_bound", transport=self._transport, with_evdev=True)
        else:
            logger.info(
                "controller_primary_bound",
                transport=self._transport,
                with_evdev=False,
                hint="input pode ficar zerado se kernel hid_playstation capturar evdev",
            )

    def disconnect(self) -> None:
        with contextlib.suppress(Exception):
            self._evdev.stop()
        with self._io_lock:
            for key in list(self._handles):
                handle = self._handles.pop(key)
                with contextlib.suppress(Exception):
                    handle.close()
            self._primary_key = None

    def is_connected(self) -> bool:
        # "Qualquer controle conectado". `ds.connected` é o canônico do
        # pydualsense (bool). AUDIT-FINDING-LOG-EXC-INFO-01: default conservador
        # `False` quando o atributo está ausente (estado desconhecido).
        with self._io_lock:
            handles = list(self._handles.values())
        return any(bool(getattr(h, "connected", False)) for h in handles)

    def heal_evdev_if_stale(self) -> bool:
        """Watchdog HID x evdev: se o evdev reader ficou preso num node OBSOLETO
        (re-enumeração pós storm -71 / replug, sem ENODEV), força reabrir.

        Retorna True se disparou o reopen. No-op (False) sem reader disponível.
        FEAT-DSX-EVDEV-WATCHDOG-01 — chamado pelo poll loop só com o HID
        conectado (o cross-check) e em intervalo throttled (escaneia /dev/input).
        """
        if not self._evdev.is_available():
            return False
        if self._evdev.is_stale():
            self._evdev.request_reopen("hid_connected_but_evdev_node_changed")
            return True
        return False

    def read_state(self) -> ControllerState:
        # INPUT vem SEMPRE do controle PRIMÁRIO (`self._ds`). Emulação de
        # mouse/teclado/gamepad é, portanto, single-controller por construção.
        ds = self._ds
        # BUG-DAEMON-NO-DEVICE-FATAL-01: quando offline, devolve snapshot
        # neutro em vez de levantar. Daemon segue rodando o poll_loop e
        # publica estado vazio para CLI/GUI/IPC.
        if ds is None:
            return ControllerState(
                battery_pct=0,
                l2_raw=0,
                r2_raw=0,
                connected=False,
                transport=self._transport,
                raw_lx=128,
                raw_ly=128,
                raw_rx=128,
                raw_ry=128,
                buttons_pressed=frozenset(),
            )
        # BUG-TRANSPORT-CACHE-STALE-01 (v3.2.1): re-detecta transport a cada
        # tick em vez de só no connect(). Quando o controle troca USB <-> BT
        # sem desconectar (cabo plugado/desplugado com BT pareado), o
        # pydualsense atualiza `conType` mas o cached `_transport` ficava
        # stale, fazendo a CLI/GUI mostrarem o transporte errado por horas.
        # Custo: 1 getattr + 1 string check por tick (~60Hz) — desprezível.
        self._transport = self._detect_transport(ds)
        battery = self._read_battery_raw(ds)
        # HOTFIX-2: evdev é fonte primária de input quando disponível.
        if self._evdev.is_available():
            snap = self._evdev.snapshot()
            # Consolida botões: evdev (ramo primário) + HID-raw do Mic (INFRA-MIC-HID-01).
            # O botão Mic não tem keycode evdev estável — vem por `ds.state.micBtn`
            # (byte misc2, bit 0x04). Tratamento defensivo: primeiro tick pode
            # ter state cru antes do firmware enviar o primeiro report completo.
            buttons = set(snap.buttons_pressed)
            try:
                if bool(getattr(ds.state, "micBtn", False)):
                    buttons.add("mic_btn")
            except AttributeError:  # state cru no primeiro tick — ds.state pode faltar atributos
                logger.debug("ds_state_mic_btn_indisponivel_evdev_path", exc_info=True)
            buttons_pressed = frozenset(buttons)
            return ControllerState(
                battery_pct=battery,
                l2_raw=snap.l2_raw,
                r2_raw=snap.r2_raw,
                connected=self.is_connected(),
                transport=self._transport,
                raw_lx=snap.lx,
                raw_ly=snap.ly,
                raw_rx=snap.rx,
                raw_ry=snap.ry,
                buttons_pressed=buttons_pressed,
            )
        # Fallback pydualsense: HOTFIX-1 corrigiu os atributos, mas em
        # runtime com hid_playstation ativo os valores não atualizam.
        # Sem evdev, botões evdev ficam vazios; apenas `micBtn` (HID-raw) é
        # garantido pelo pydualsense mesmo neste ramo.
        state = ds.state
        l2_raw = int(getattr(state, "L2_value", 0)) & 0xFF
        r2_raw = int(getattr(state, "R2_value", 0)) & 0xFF
        buttons_fallback: frozenset[str] = frozenset()
        try:
            if bool(getattr(state, "micBtn", False)):
                buttons_fallback = frozenset({"mic_btn"})
        except AttributeError:
            logger.debug("ds_state_mic_btn_indisponivel_fallback_path", exc_info=True)
        return ControllerState(
            battery_pct=battery,
            l2_raw=l2_raw,
            r2_raw=r2_raw,
            connected=self.is_connected(),
            transport=self._transport,
            raw_lx=int(state.LX) & 0xFF,
            raw_ly=int(state.LY) & 0xFF,
            raw_rx=int(state.RX) & 0xFF,
            raw_ry=int(state.RY) & 0xFF,
            buttons_pressed=buttons_fallback,
        )

    # --- output (fan-out p/ TODOS os controles) -------------------------

    def _for_each(self, op: Callable[[pydualsense], None], *, what: str) -> None:
        """Aplica `op` ao ALVO de output (ou a cada handle aberto, em broadcast).

        FEAT-DSX-CONTROLLER-SELECTOR-01: se `_output_target_key` está setada E o
        controle ainda está presente em `_handles`, aplica SÓ a esse handle;
        senão (sem alvo, ou alvo desconectou), volta ao broadcast histórico —
        TODOS os controles. 1 handle morto não derruba os outros.

        Tira um snapshot da lista sob `_io_lock` e faz o HID I/O fora da seção
        crítica (não segura o lock durante a escrita no device).
        """
        with self._io_lock:
            target = self._output_target_key
            if target is not None and target in self._handles:
                handles = [(target, self._handles[target])]
            else:
                handles = list(self._handles.items())
        if not handles:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in handles:
            try:
                op(handle)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    @staticmethod
    def _apply_trigger(handle: pydualsense, side: Side, effect: TriggerEffect) -> None:
        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = PyDualSenseController._coerce_mode(effect.mode)
        for idx, value in enumerate(effect.forces):
            trigger.setForce(idx, value)

    def _reapply_desired(self, handle: pydualsense) -> None:
        """Re-aplica o perfil ativo (`_desired`) num handle recém-aberto."""
        from pydualsense.enums import PlayerID

        desired = self._desired
        try:
            if desired.trigger_left is not None:
                self._apply_trigger(handle, "left", desired.trigger_left)
            if desired.trigger_right is not None:
                self._apply_trigger(handle, "right", desired.trigger_right)
            if desired.led is not None:
                handle.light.setColorI(*desired.led)
            if desired.player_leds is not None:
                mask = sum(1 << i for i, b in enumerate(desired.player_leds) if b)
                handle.light.playerNumber = PlayerID(mask)
            if desired.mic_led is not None:
                handle.audio.setMicrophoneLED(desired.mic_led)
        except Exception as exc:
            logger.warning("reapply_perfil_no_hotplug_falhou", err=str(exc))

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        if side == "left":
            self._desired.trigger_left = effect
        else:
            self._desired.trigger_right = effect
        self._for_each(lambda h: self._apply_trigger(h, side, effect), what="set_trigger")

    def set_led(self, color: tuple[int, int, int]) -> None:
        self._desired.led = color
        r, g, b = color
        self._for_each(lambda h: h.light.setColorI(r, g, b), what="set_led")

    def set_rumble(self, weak: int, strong: int) -> None:
        # Rumble é TRANSITÓRIO (efeito de jogo) — NÃO entra em `_desired`, logo
        # não é "ressuscitado" num controle plugado depois.
        def _do(handle: pydualsense) -> None:
            handle.setLeftMotor(strong)
            handle.setRightMotor(weak)

        self._for_each(_do, what="set_rumble")

    def set_mic_led(self, muted: bool) -> None:
        """Acende/apaga o LED do microfone em TODOS os controles (INFRA-SET-MIC-LED-01).

        Delega para `ds.audio.setMicrophoneLED(bool)`. A pydualsense cuida da
        diferença USB/BT em `prepareReport` (outReport[9] USB / outReport[10] BT).
        """
        flag = bool(muted)
        self._desired.mic_led = flag
        self._for_each(lambda h: h.audio.setMicrophoneLED(flag), what="set_mic_led")

    def set_player_leds(self, bits: tuple[bool, bool, bool, bool, bool]) -> None:
        """Aplica bitmask de 5 LEDs de player em TODOS os controles.

        `pydualsense.DSLight.playerNumber` é do tipo `PlayerID` (`IntFlag`), que
        aceita qualquer valor inteiro — não apenas os 4 canônicos (4, 10, 21, 27).
        Isso permite combinações arbitrárias de LEDs sem acesso HID bruto.

        O bitmask é montado como:
          bit0 = bits[0] (LED 1, extremo esquerdo)
          bit1 = bits[1] (LED 2)
          bit2 = bits[2] (LED 3, central — o LED do Player 1 canônico)
          bit3 = bits[3] (LED 4)
          bit4 = bits[4] (LED 5, extremo direito)

        Referência: outReport[44] (USB) / outReport[45] (BT) em
        pydualsense/pydualsense.py:572/636 — recebe `self.light.playerNumber.value`.
        """
        from pydualsense.enums import PlayerID

        self._desired.player_leds = bits
        bitmask = sum(1 << i for i, b in enumerate(bits) if b)
        self._for_each(
            lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
            what="set_player_leds",
        )
        logger.debug("player_leds_aplicados bits=%s bitmask=%s", list(bits), bitmask)

    # --- introspecção / leitura do primário -----------------------------

    def describe_controllers(self) -> list[dict[str, object]]:
        """Descreve cada controle conectado (observabilidade — IPC `controller.list`).

        Uma entrada por handle aberto: `{index, connected, transport, is_primary}`.
        O `index` (FEAT-DSX-CONTROLLER-SELECTOR-01) é a POSIÇÃO em
        `list(self._handles)` (0 = primário) — o mesmo número que o seletor de
        controle usa em `set_output_target`. Quando nenhum controle está
        conectado, devolve uma única entrada offline (preserva o contrato "ao
        menos um item" do handler legado).
        """
        with self._io_lock:
            items = list(self._handles.items())
            primary = self._primary_key
        if not items:
            return [{"connected": False, "transport": None, "is_primary": False}]
        out: list[dict[str, object]] = []
        for idx, (key, handle) in enumerate(items):
            connected = bool(getattr(handle, "connected", False))
            out.append(
                {
                    "index": idx,
                    "connected": connected,
                    "transport": self._detect_transport(handle) if connected else None,
                    "is_primary": key == primary,
                }
            )
        return out

    def set_output_target(self, index: int | None) -> int | None:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01).

        `index` é a POSIÇÃO em `list(self._handles)` (0 = primário); guardamos a
        KEY estável (serial/MAC) correspondente — NÃO o índice — para o alvo
        sobreviver a hotplug/troca de porta. `None` ou fora de faixa → broadcast
        (TODOS, padrão). Devolve o índice efetivo (ou None para "todos"). Sob
        `_io_lock` (consistente com o snapshot que o `_for_each` tira).
        """
        with self._io_lock:
            if index is None:
                self._output_target_key = None
                return None
            keys = list(self._handles)
            if not (0 <= index < len(keys)):
                self._output_target_key = None
                return None
            self._output_target_key = keys[index]
            return index

    def get_output_target_index(self) -> int | None:
        """Posição atual do alvo de output, ou None (FEAT-DSX-CONTROLLER-SELECTOR-01).

        Mapeia a KEY guardada para a posição em `list(self._handles)`; devolve
        None quando o alvo é "todos" (broadcast) ou quando o controle alvo sumiu
        (desconectou) — caso em que o `_for_each` já voltou ao broadcast.
        """
        with self._io_lock:
            key = self._output_target_key
            if key is None or key not in self._handles:
                return None
            return list(self._handles).index(key)

    def get_battery(self) -> int:
        ds = self._ds
        if ds is None:
            return 0
        return self._read_battery_raw(ds)

    def get_transport(self) -> Transport:
        return self._transport

    def _require(self) -> pydualsense:
        ds = self._ds
        if ds is None:
            raise RuntimeError("pydualsense não inicializado — chamar connect() antes")
        return ds

    @staticmethod
    def _detect_transport(ds: pydualsense) -> Transport:
        con = getattr(ds, "conType", None)
        if con is None:
            return "usb"
        name = str(getattr(con, "name", con)).lower()
        return "usb" if "usb" in name else "bt"

    @staticmethod
    def _read_battery_raw(ds: pydualsense) -> int:
        # HOTFIX-1: battery vive em `ds.battery` (top-level), não em ds.state.
        # DSBattery expõe `Level` (0-100) e `State` (enum BatteryState).
        battery = getattr(ds, "battery", None)
        if battery is None:
            return 0
        level = getattr(battery, "Level", None)
        if level is None:
            return 0
        try:
            value = int(level)
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, value))

    @staticmethod
    def _coerce_mode(mode: int) -> object:
        from pydualsense.enums import TriggerModes
        try:
            return TriggerModes(mode)
        except ValueError:
            logger.warning("trigger_mode_fora_do_enum_mantendo_raw", mode=mode)
            return mode


__all__ = ["PyDualSenseController"]
