"""Espelho de MOTION: hidraw cru do DualSense físico → vpad uhid (GYRO-01).

Por que este módulo existe
--------------------------
O vpad uhid (máscara DualSense Edge) monta o report 0x01 a partir do evdev do
físico — sticks/botões/d-pad — e deixava a janela de motion (bytes 15..39 do
payload: gyro, accel, sensor_timestamp e os 2 pontos de toque) NEUTRA. Medido
ao vivo (2026-07-19): o físico emite gyro a 250 Hz (USB) / ~765 Hz (BT) e o nó
Motion do vpad emite ZERO — gyro aiming morto para quem joga pelo hefesto.

A cura é um espelho de report PARCIAL (ARCH-1 do estudo
`docs/process/estudos/2026-07-18-estudo-imu-touchpad-vpad.md`): uma thread
abre um 2º fd SOMENTE-LEITURA no hidraw do físico, extrai VERBATIM a janela
`raw[base+15 : base+40]` de cada report cru (0x01 USB, base 1; 0x31 BT, base 2
com CRC-32 validado — seed 0xA1, o `PS_INPUT_CRC32_SEED` do kernel) e a entrega
em `vpad.forward_motion(window)`. Cópia byte a byte: zero matemática, e o
`sensor_timestamp` (que o SDL usa como dt de integração do gyro e que o evdev
NÃO expõe) vem de graça. Sticks/botões continuam no caminho evdev endurecido.

O reader é o RELÓGIO: ao abrir o device ele liga `set_motion_streaming(True)`
no vpad — os forwards do poll loop (60 Hz) viram só-cache e cada janela nova
sai na taxa do físico, com throttle. Ao perder o device (hotplug, BT caiu,
retarget) desliga o streaming: o vpad volta ao delta de 60 Hz com IMU neutra —
fail-safe por construção, nunca um gyro congelado.

Throttle (obrigatório, não otimização): o BT desta máquina entrega ~765 Hz por
controle; sem cap, 4 vpads em co-op seriam ~3000 writes/s no /dev/uhid. A
emissão é capada em `MOTION_EMIT_MAX_HZ` (250 Hz — a taxa nativa USB, e a
mesma faixa do rate-limit do REPLICA-03) com dedup por valor e COALESCÊNCIA:
janela retida é sobrescrita pela mais nova e a última nunca se perde (flush no
timeout do select). Jogos integram gyro bem em 250 Hz; o timestamp do sensor
segue exato em cada janela entregue.

Leitura NÃO reabre a guerra de escritores: a guerra (2026-07-18) é sobre
WRITERS no hidraw; o kernel replica cada input report para TODOS os fds
abertos (fila própria por leitor) — este fd O_RDONLY não rouba nada da
pydualsense nem do jogo, e não gera tráfego novo de rádio/USB.
"""
from __future__ import annotations

import contextlib
import os
import select
import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Report de input do DualSense por transporte (hid-playstation.c):
#: USB = 0x01 (64 B, payload começa em data[1]); BT = 0x31 (78 B, payload em
#: data[2] — 0x31 + 1 byte de header — e CRC-32 nos 4 últimos bytes).
INPUT_REPORT_USB = 0x01
INPUT_REPORT_BT = 0x31
INPUT_REPORT_BT_SIZE = 78
_USB_STRUCT_BASE = 1
_BT_STRUCT_BASE = 2

#: Janela de motion DENTRO do payload (offsets do `struct dualsense_input_
#: report`): gyro[3] 15-20, accel[3] 21-26, sensor_timestamp 27-30, reserved2
#: 31, touch points 32-39. Mesmos números do `_MOTION_WINDOW` do vpad
#: (`integrations/uhid_gamepad.py`) — travados um no outro por teste.
MOTION_WINDOW_OFFSET = 15
MOTION_WINDOW_LEN = 25

#: Cap da taxa de emissão ao vpad. 250 Hz = taxa nativa do físico em USB (nada
#: é jogado fora no cabo) e o mesmo teto do rate-limit do REPLICA-03; em BT
#: (~765 Hz) vira downsample com coalescência — o estudo aceita 250-500 Hz.
MOTION_EMIT_MAX_HZ = 250.0

#: Tamanho de leitura: cobre 64 (USB) e 78 (BT) com folga.
_READ_LEN = 128

#: Timeout do select por iteração — o teto de latência para ver o stop_flag e
#: para o flush da janela retida pelo throttle quando o fluxo para.
_SELECT_TIMEOUT_S = 0.25

#: Silêncio máximo com o fd aberto antes de declarar o físico mudo e reabrir.
#: Um DualSense vivo emite SEMPRE (250-765 Hz); 1 s de silêncio = link morto
#: ou nó obsoleto — larga o fd, desliga o streaming (fail-safe p/ 60 Hz) e
#: re-resolve o path (o provider aponta o primário ATUAL).
_SILENCE_REOPEN_S = 1.0

#: Backoff de reconexão (mesma curva do `_EvdevReconnectLoop`).
_BACKOFF_START_S = 0.5
_BACKOFF_MAX_S = 5.0

#: Telemetria GYRO-03 — taxa de emissão (`emit_hz`) por EMA dos intervalos
#: entre entregas. Alpha 0.25 ≈ estabiliza em ~1 s a 250 Hz sem congelar em
#: transientes; acima de `_HZ_STALE_S` sem entrega a taxa reportada é 0.0
#: (uma EMA "congelada" de um fluxo morto mentiria 250 Hz para sempre).
_HZ_EMA_ALPHA = 0.25
_HZ_STALE_S = 1.0


def _novo_wake_pipe() -> tuple[int, int]:
    """Par de self-pipe (não-bloqueante) para acordar o select do reader.

    GYRO-FD-01: `stop()`/`request_reopen()` NUNCA fecham o fd do hidraw de
    fora — só escrevem 1 byte aqui. Fechar de fora libera o NÚMERO do fd
    enquanto a thread ainda está em select/read nele; qualquer open
    concorrente do daemon (eventX do `_recompute_primary`, /dev/uhid de um
    vpad novo) recicla o número e o reader passa a drenar um fd ALHEIO —
    input do jogo congela e a janela fatiada vira gyro-lixo no vpad.
    """
    lado_r, lado_w = os.pipe()
    os.set_blocking(lado_r, False)
    os.set_blocking(lado_w, False)
    return lado_r, lado_w


def extract_motion_window(report: bytes) -> bytes | None:
    """Janela de motion (25 B) de um report CRU do físico, ou None.

    - ``0x01`` (USB): payload em ``report[1:]`` → janela = ``report[16:41]``.
    - ``0x31`` (BT): exige os 78 B exatos e CRC-32 válido (seed 0xA1 sobre os
      74 primeiros bytes, LE nos 4 finais — `ps_check_crc32` do kernel); um
      CRC ruim é rádio corrompido e NÃO pode virar motion no vpad. Janela =
      ``report[17:42]``.
    - Qualquer outro id/tamanho (0x05 de BT parcial, reports de feature) → None.
    """
    if not report:
        return None
    if report[0] == INPUT_REPORT_USB:
        start = _USB_STRUCT_BASE + MOTION_WINDOW_OFFSET
        end = start + MOTION_WINDOW_LEN
        if len(report) < end:
            return None
        return bytes(report[start:end])
    if report[0] == INPUT_REPORT_BT:
        if len(report) != INPUT_REPORT_BT_SIZE:
            return None
        crc = int.from_bytes(report[-4:], "little")
        if bt_crc32(report[:-4], seed=BT_INPUT_CRC_SEED) != crc:
            return None
        start = _BT_STRUCT_BASE + MOTION_WINDOW_OFFSET
        return bytes(report[start : start + MOTION_WINDOW_LEN])
    return None


class PhysicalReportReader:
    """Thread que espelha a janela de motion do hidraw físico no vpad.

    `path_provider` (e não um path fixo) é a chave do retarget: a cada
    (re)abertura o reader pergunta "qual é o hidraw AGORA?" — troca de
    primário, reconexão BT e re-enumeração convergem sozinhas, e
    `request_reopen()` (chamado pelo backend em `_recompute_primary`) só
    precisa SINALIZAR (flag + self-pipe) para a própria thread largar o fd
    e a próxima volta resolver o nó certo — nunca um close de fora
    (GYRO-FD-01: número de fd liberado sob select seria reciclável).

    O contrato com o vpad são dois métodos: `set_motion_streaming(bool)` nas
    bordas abrir/perder e `forward_motion(window)` por janela (já throttled).
    """

    def __init__(
        self,
        path_provider: Callable[[], str | None],
        vpad: Any,
        *,
        max_hz: float = MOTION_EMIT_MAX_HZ,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path_provider = path_provider
        self._vpad = vpad
        self._min_interval = 1.0 / float(max_hz) if max_hz > 0 else 0.0
        self._time_fn = time_fn
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None
        # fd ativo — a thread do reader é a ÚNICA dona (abre, usa e fecha).
        # Quem está fora só SINALIZA (flag + 1 byte no self-pipe): fechar de
        # fora liberaria o número do fd com a thread ainda em select/read
        # nele, e um open concorrente do daemon poderia RECICLAR o número
        # (reader drenando fd alheio = input congelado + gyro-lixo).
        self._fd: int | None = None
        self._fd_lock = threading.Lock()
        # Self-pipe de wake + flag de reopen (GYRO-FD-01). O par é recriado
        # no `start()` se um `stop()` anterior o fechou. O lock cobre a
        # corrida `_wake()` vs `_close_wake_pipe()`: escrever num número já
        # fechado/reciclado seria o mesmo defeito em miniatura.
        self._reopen_flag = threading.Event()
        self._wake_lock = threading.Lock()
        self._wake_r, self._wake_w = _novo_wake_pipe()
        # Throttle: último valor ENTREGUE (dedup), retido (coalescência) e o
        # instante da última entrega.
        self._last_window: bytes | None = None
        self._pending: bytes | None = None
        self._last_emit_at = float("-inf")
        # Telemetria (GYRO-03 lê): reports vistos, janelas emitidas, drops de
        # CRC/tamanho no caminho BT e a taxa de emissão (EMA em Hz).
        self._reports_seen = 0
        self._windows_emitted = 0
        self._bt_drops = 0
        self._emit_hz_ema = 0.0

    # -- telemetria -------------------------------------------------------

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def reports_seen(self) -> int:
        return self._reports_seen

    @property
    def windows_emitted(self) -> int:
        return self._windows_emitted

    @property
    def bt_drops(self) -> int:
        return self._bt_drops

    @property
    def emit_hz(self) -> float:
        """Taxa de emissão ao vpad (Hz, EMA) — 0.0 quando o fluxo parou.

        GYRO-03: é ESTA taxa (pós-throttle, o que o vpad de fato recebe) que
        o `state_full` publica como `motion_hz`. "Parou" = nenhuma entrega há
        mais de `_HZ_STALE_S` — a EMA antiga de um fluxo morto não vale nada.
        """
        if self._emit_hz_ema <= 0.0:
            return 0.0
        if (self._time_fn() - self._last_emit_at) > _HZ_STALE_S:
            return 0.0
        return round(self._emit_hz_ema, 1)

    # -- ciclo de vida ----------------------------------------------------

    def start(self) -> bool:
        """Sobe a thread (idempotente). O device é aberto DENTRO do loop."""
        if self.is_running:
            return True
        self._stop_flag.clear()
        self._reopen_flag.clear()
        if self._wake_r < 0 or self._wake_w < 0:
            # Um stop() anterior fechou o self-pipe — recria para esta vida.
            self._wake_r, self._wake_w = _novo_wake_pipe()
        player = getattr(self._vpad, "player", "?")
        self._thread = threading.Thread(
            target=self._run, name=f"hefesto-motion-p{player}", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Para a thread e garante o streaming DESLIGADO no vpad.

        Chamar ANTES do `stop()` do vpad (ordem do teardown): o reader escreve
        no /dev/uhid via `forward_motion` e não pode sobreviver ao fd do device.

        GYRO-FD-01: NÃO fecha o fd do hidraw — só sinaliza (flag + wake) e a
        própria thread fecha o fd dela no finally. O wake acorda o select na
        hora (sem esperar o timeout da iteração).
        """
        self._stop_flag.set()
        self._wake()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
            if not thread.is_alive():
                # Thread morta de verdade: o self-pipe pode ir sem risco de
                # reciclagem (o start() recria se este reader voltar).
                self._close_wake_pipe()
        else:
            self._close_wake_pipe()
        # Idempotente com o finally do loop — cinto e suspensório: o vpad não
        # pode ficar em streaming sem reader vivo (input congelaria no jogo).
        with contextlib.suppress(Exception):
            self._vpad.set_motion_streaming(False)

    def request_reopen(self, reason: str = "retarget") -> None:
        """Pede à thread que largue o fd atual e reabra pelo `path_provider`.

        Barato e não-bloqueante de propósito: o backend chama isto de dentro
        do `_recompute_primary` (sob o `_io_lock` dele). GYRO-FD-01: NUNCA
        toca o fd — fechar de fora liberaria o número com a thread ainda em
        select/read e um open concorrente o reciclaria (fd alheio drenado).
        """
        logger.info("motion_reader_reopen_requested", reason=reason)
        self._reopen_flag.set()
        self._wake()

    def _wake(self) -> None:
        """1 byte no self-pipe: acorda o select da thread imediatamente."""
        with self._wake_lock:
            if self._wake_w >= 0:
                with contextlib.suppress(OSError):
                    os.write(self._wake_w, b"w")

    def _drain_wake(self) -> None:
        """Esvazia o self-pipe (não-bloqueante; bytes velhos não acumulam)."""
        with contextlib.suppress(OSError):
            while os.read(self._wake_r, 64):
                pass

    def _close_wake_pipe(self) -> None:
        with self._wake_lock:
            for attr in ("_wake_r", "_wake_w"):
                fd = getattr(self, attr)
                if fd >= 0:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                    setattr(self, attr, -1)

    def _close_fd(self, _reason: str) -> None:
        """Fecha o fd do hidraw — chamado SOMENTE pela thread do reader."""
        with self._fd_lock:
            fd, self._fd = self._fd, None
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)

    # -- loop -------------------------------------------------------------

    def _run(self) -> None:
        backoff = _BACKOFF_START_S
        while not self._stop_flag.is_set():
            # Pedido de reopen anterior a este resolve já está atendido POR
            # este resolve (o provider aponta o alvo ATUAL); um set depois
            # do clear é pedido novo e derruba o fd na 1ª iteração do loop.
            self._reopen_flag.clear()
            path = self._resolve_path()
            if path is None:
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, _BACKOFF_MAX_S)
                continue
            try:
                fd = os.open(path, os.O_RDONLY)
            except OSError as exc:
                logger.warning("motion_reader_open_failed", path=path, err=str(exc))
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, _BACKOFF_MAX_S)
                continue
            with self._fd_lock:
                self._fd = fd
            backoff = _BACKOFF_START_S
            logger.info("motion_reader_started", path=path)
            with contextlib.suppress(Exception):
                self._vpad.set_motion_streaming(True)
            try:
                self._read_until_lost(fd)
            finally:
                self._close_fd("read_lost")
                # Fail-safe: sem fonte de motion o vpad volta ao ritmo do poll
                # com IMU neutra (nunca um gyro congelado na mira do jogo).
                with contextlib.suppress(Exception):
                    self._vpad.set_motion_streaming(False)
            if not self._stop_flag.is_set():
                time.sleep(0.1)  # graça antes de reabrir (padrão do evdev)

    def _resolve_path(self) -> str | None:
        try:
            path = self._path_provider()
        except Exception as exc:
            logger.debug("motion_reader_provider_failed", err=str(exc))
            return None
        return path if isinstance(path, str) and path else None

    def _read_until_lost(self, fd: int) -> None:
        """Lê reports até o fd morrer (ENODEV), silêncio longo ou sinal de fora.

        GYRO-FD-01: o select vigia TAMBÉM o self-pipe — `stop()` e
        `request_reopen()` acordam a thread na hora sem nunca fechar o fd
        (que é fechado pelo finally do `_run`, sempre pela própria thread).
        """
        silencio = 0.0
        while not self._stop_flag.is_set():
            if self._reopen_flag.is_set():
                # Sinal que chegou fora do select (ex.: entre o open e a 1ª
                # iteração): larga o fd para o loop re-resolver o alvo.
                self._reopen_flag.clear()
                return
            try:
                pronto, _, _ = select.select(
                    [fd, self._wake_r], [], [], _SELECT_TIMEOUT_S
                )
            except (OSError, ValueError):
                return  # fd morreu debaixo do select (ENODEV de hotplug)
            if self._wake_r in pronto:
                self._drain_wake()
                if self._stop_flag.is_set():
                    return
                if self._reopen_flag.is_set():
                    self._reopen_flag.clear()
                    return
                continue  # byte velho de um wake já atendido — segue
            if not pronto:
                silencio += _SELECT_TIMEOUT_S
                self._flush_pending()
                if silencio >= _SILENCE_REOPEN_S:
                    # Um DualSense vivo NUNCA silencia por 1 s — nó obsoleto ou
                    # link morto. Larga e re-resolve (o provider re-aponta).
                    logger.info("motion_reader_silencio_reabrindo")
                    return
                continue
            silencio = 0.0
            try:
                data = os.read(fd, _READ_LEN)
            except OSError:
                return  # ENODEV: hotplug-out (o fd é sempre o NOSSO, vivo)
            if not data:
                return
            self._reports_seen += 1
            window = extract_motion_window(data)
            if window is None:
                if data[0] == INPUT_REPORT_BT:
                    self._bt_drops += 1
                continue
            self._maybe_emit(window)

    # -- throttle ---------------------------------------------------------

    def _maybe_emit(self, window: bytes, now: float | None = None) -> None:
        """Dedup por valor + cap de taxa com coalescência do último valor."""
        if window == self._last_window:
            return
        if now is None:
            now = self._time_fn()
        if (now - self._last_emit_at) < self._min_interval:
            # Retida pelo cap — a mais nova SEMPRE sobrescreve (coalescência);
            # sai no próximo report pós-janela ou no flush do select-timeout.
            self._pending = window
            return
        self._pending = None
        self._emit(window, now)

    def _flush_pending(self, now: float | None = None) -> None:
        """Entrega a janela retida quando o cap venceu e o fluxo parou."""
        pending = self._pending
        if pending is None:
            return
        if now is None:
            now = self._time_fn()
        if (now - self._last_emit_at) < self._min_interval:
            return
        self._pending = None
        if pending == self._last_window:
            return
        self._emit(pending, now)

    def _emit(self, window: bytes, now: float) -> None:
        # EMA da taxa ANTES de carimbar o novo instante (o intervalo é entre
        # a entrega anterior e esta). A 1ª entrega não tem intervalo (last é
        # -inf) e a EMA fica em 0 até a 2ª.
        intervalo = now - self._last_emit_at
        if 0.0 < intervalo < _HZ_STALE_S:
            inst = 1.0 / intervalo
            self._emit_hz_ema = (
                inst
                if self._emit_hz_ema <= 0.0
                else _HZ_EMA_ALPHA * inst + (1.0 - _HZ_EMA_ALPHA) * self._emit_hz_ema
            )
        elif intervalo >= _HZ_STALE_S:
            # Fluxo voltou depois de um buraco: recomeça a medição do zero
            # (misturar a EMA de antes do buraco distorceria a taxa nova).
            self._emit_hz_ema = 0.0
        self._last_emit_at = now
        self._last_window = window
        try:
            self._vpad.forward_motion(window)
            self._windows_emitted += 1
        except Exception as exc:
            logger.warning("motion_reader_forward_failed", err=str(exc))


__all__ = [
    "INPUT_REPORT_BT",
    "INPUT_REPORT_BT_SIZE",
    "INPUT_REPORT_USB",
    "MOTION_EMIT_MAX_HZ",
    "MOTION_WINDOW_LEN",
    "MOTION_WINDOW_OFFSET",
    "PhysicalReportReader",
    "extract_motion_window",
]
