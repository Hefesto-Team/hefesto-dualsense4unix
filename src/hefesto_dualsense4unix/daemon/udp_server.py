"""UDP server compatível com o protocolo DSX (V2 5.10, ADR-003, V3-1)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.core.trigger_effects import off as trigger_off
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6969
MAX_DATAGRAM_BYTES = 4096

RATE_GLOBAL = 2000
RATE_PER_IP = 1000
SUPPORTED_VERSION = 1

DSX_TRIGGER_SIDES = {1: "left", 2: "right"}

#:   - `WujekFoliarz/DualSenseY-v2` `include/udp.hpp`  TriggerThreshold = 4
#: a maioria de 3 contra 1 — e o desempate real é que o DualSenseY-v2 é um
DSX_INSTRUCTION_TYPES: dict[int, str] = {
    1: "TriggerUpdate",
    2: "RGBUpdate",
    3: "PlayerLED",
    4: "TriggerThreshold",
    5: "MicLED",
    7: "ResetToUserSettings",
}

#: Os ordinais 20-26 são a extensão do DualSenseY-v2 e usam nomes que são
DSX_TRIGGER_MODES: dict[int, str] = {
    0: "Off",
    13: "Resistance",
    14: "Bow",
    15: "Galloping",
    16: "SemiAutoGun",
    17: "AutoGun",
    18: "Machine",
    20: "Off",
    21: "Feedback",
    22: "Weapon",
    23: "Vibration",
    24: "SlopeFeedback",
    25: "MultiPositionFeedback",
    26: "MultiPositionVibration",
}

DSX_TRIGGER_MODE_CUSTOM_VALUE = 12

#: dessas tabelas que encontrei está no `DualSenseY-v2`, que é um repositório
DSX_CANNED_TRIGGER_MODES: dict[int, str] = {
    1: "GameCube",
    2: "VerySoft",
    3: "Soft",
    4: "Hard",
    5: "VeryHard",
    6: "Hardest",
    7: "Rigid",
    8: "VibrateTrigger",
    9: "Choppy",
    10: "Medium",
    11: "VibrateTriggerPulse",
    19: "VibrateTrigger10Hz",
}

DSX_CUSTOM_VALUE_MODES: dict[int, int] = {
    0: 0x00,
    1: 0x01,
    2: 0x01 | 0x20,
    3: 0x01 | 0x04,
    4: 0x01 | 0x20 | 0x04,
    5: 0x02,
    6: 0x02 | 0x20,
    7: 0x02 | 0x04,
    8: 0x02 | 0x20 | 0x04,
}

DSX_MIC_LED_MODES: dict[int, bool] = {0: True, 1: True, 2: False}
DSX_MIC_LED_PULSE = 1


def resolve_instruction_type(raw: object) -> str | None:
    """Nome canônico da instrução a partir de `type`. `None` = irreconhecível."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, int):
        return DSX_INSTRUCTION_TYPES.get(raw)
    return None


def resolve_dsx_trigger_mode(
    raw_mode: object, rest: list[Any]
) -> tuple[str, list[Any]]:
    """Traduz `(TriggerMode do DSX, params)` para `(preset do Hefesto, params)`."""
    ordinal = int(raw_mode)  # type: ignore[call-overload]
    if ordinal == DSX_TRIGGER_MODE_CUSTOM_VALUE:
        if not rest:
            raise ValueError(
                "TriggerUpdate CustomTriggerValue precisa do modo + forcas"
            )
        hid = DSX_CUSTOM_VALUE_MODES.get(int(rest[0]))
        if hid is None:
            raise ValueError(
                f"TriggerUpdate CustomTriggerValueMode {int(rest[0])} sem "
                "equivalente no Hefesto (variantes VibrateResistance/VibratePulse)"
            )
        forcas = [int(v) for v in rest[1:8]]
        forcas += [0] * (7 - len(forcas))
        return "Custom", [hid, *forcas]
    preset = DSX_TRIGGER_MODES.get(ordinal)
    if preset is not None:
        return preset, list(rest)
    prontos = DSX_CANNED_TRIGGER_MODES.get(ordinal)
    if prontos is not None:
        raise ValueError(
            f"TriggerUpdate modo DSX {prontos!r} ({ordinal}) não implementado: "
            "e uma curva de forca fechada do DSX, sem parametros e sem tabela "
            "de bytes publicada sob licenca utilizavel"
        )
    raise ValueError(f"TriggerUpdate modo DSX desconhecido: {ordinal}")


def parse_side(raw: object) -> str | None:
    """Traduz o lado do gatilho nos dois dialetos aceitos. `None` = inválido."""
    if isinstance(raw, str):
        texto = raw.strip().lower()
        if texto in ("left", "right"):
            return texto
        if texto.isdigit():
            return DSX_TRIGGER_SIDES.get(int(texto))
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return DSX_TRIGGER_SIDES.get(raw)
    return None


def parse_side_and_value(
    params: list[Any], *, kind: str
) -> tuple[str, int, int | None]:
    """Extrai `(lado, valor, índice)` dos dois layouts que chegam na 6969."""
    if len(params) < 2:
        raise ValueError(f"{kind} precisa [side, value]")
    if len(params) >= 3:
        lado = parse_side(params[1])
        if lado is not None:
            return lado, int(params[2]), _como_indice(params[0])
    lado = parse_side(params[0])
    if lado is None:
        raise ValueError(f"{kind} side invalido: {params[0]!r}")
    return lado, int(params[1]), None


def _como_indice(raw: object) -> int | None:
    """`controllerIndex` como inteiro, ou `None` quando não for um."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class RateLimiter:
    """Dois limites sobrepostos: global + per-IP (V3-1)."""

    def __init__(
        self,
        rate_global: int = RATE_GLOBAL,
        rate_per_ip: int = RATE_PER_IP,
    ) -> None:
        self.rate_global = rate_global
        self.rate_per_ip = rate_per_ip
        self.global_window: deque[float] = deque(maxlen=rate_global)
        self.per_ip: dict[str, deque[float]] = {}
        self._last_sweep: float = 0.0

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < 1.0:
            return
        cutoff = now - 1.0
        self.per_ip = {
            ip: wnd
            for ip, wnd in self.per_ip.items()
            if wnd and wnd[-1] >= cutoff
        }
        self._last_sweep = now

    def allow(self, ip: str, *, now: float | None = None) -> bool:
        t = now if now is not None else time.monotonic()
        cutoff = t - 1.0
        self._sweep(t)

        while self.global_window and self.global_window[0] < cutoff:
            self.global_window.popleft()
        if len(self.global_window) >= self.rate_global:
            return False

        ip_window = self.per_ip.setdefault(ip, deque(maxlen=self.rate_per_ip))
        while ip_window and ip_window[0] < cutoff:
            ip_window.popleft()
        if len(ip_window) >= self.rate_per_ip:
            return False

        self.global_window.append(t)
        ip_window.append(t)
        return True


class DsxProtocol(asyncio.DatagramProtocol):
    def __init__(self, handler: UdpHandler) -> None:
        self.handler = handler
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.handler.handle_datagram(data, addr)


@dataclass
class UdpHandler:
    controller: IController
    store: StateStore
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    warn_limit_once_per_sec: float = 1.0
    _last_warn_at: float = 0.0

    def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        ip = addr[0]
        now = time.monotonic()
        if not self.rate_limiter.allow(ip, now=now):
            self.store.bump("udp.rate_limited")
            if now - self._last_warn_at >= self.warn_limit_once_per_sec:
                logger.warning("udp_rate_limited", ip=ip)
                self._last_warn_at = now
            return

        if len(data) > MAX_DATAGRAM_BYTES:
            self.store.bump("udp.oversize")
            logger.warning("udp_oversize", size=len(data), ip=ip)
            return

        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.store.bump("udp.parse_error")
            logger.warning("udp_parse_error", err=str(exc), ip=ip)
            return

        if not isinstance(payload, dict):
            self.store.bump("udp.parse_error")
            return

        if "version" not in payload:
            self.store.bump("udp.dsx_envelope")
        version = payload.get("version", SUPPORTED_VERSION)
        if version != SUPPORTED_VERSION:
            self.store.bump("udp.unsupported_version")
            logger.warning("udp_unsupported_version", version=version, ip=ip)
            return

        instructions = payload.get("instructions", [])
        if not isinstance(instructions, list):
            self.store.bump("udp.invalid_instructions")
            return

        for instr in instructions:
            self._dispatch_instruction(instr, ip=ip)

    def _dispatch_instruction(self, instr: dict[str, Any], *, ip: str) -> None:
        if not isinstance(instr, dict):
            self.store.bump("udp.invalid_instruction")
            return
        raw_kind = instr.get("type")
        params = instr.get("parameters", [])
        if not isinstance(params, list):
            self.store.bump("udp.invalid_instruction")
            return
        kind = resolve_instruction_type(raw_kind)
        if kind is None:
            if isinstance(raw_kind, int):
                self.store.bump("udp.unknown_instruction")
                logger.warning("udp_unknown_instruction", kind=raw_kind, ip=ip)
            else:
                self.store.bump("udp.invalid_instruction")
            return

        try:
            if kind == "TriggerUpdate":
                self._do_trigger_update(params)
            elif kind == "RGBUpdate":
                self._do_rgb_update(params)
            elif kind == "PlayerLED":
                self._do_player_led(params)
            elif kind == "MicLED":
                self._do_mic_led(params)
            elif kind == "TriggerThreshold":
                self._do_trigger_threshold(params)
            elif kind == "ResetToUserSettings":
                self._do_reset()
            else:
                self.store.bump("udp.unknown_instruction")
                logger.warning("udp_unknown_instruction", kind=kind, ip=ip)
                return
            self.store.bump(f"udp.applied.{kind}")
        except Exception as exc:
            self.store.bump(f"udp.error.{kind}")
            logger.warning("udp_instruction_error", kind=kind, err=str(exc), ip=ip)

    def _nota_indice(self, indice: int | None, *, kind: str) -> None:
        """Registra que o `controllerIndex` do DSX foi DESCARTADO.

        Índice 0 é silencioso porque é o caso normal: o SDK do DSX declara
        `public const int ControllerIndex = 0;` e todos os helpers de
        `Instruction.cs` mandam essa constante — na prática o ecossistema
        inteiro endereça o primeiro controle.

        Índice != 0 é o caso que a mantenedora tem em casa (quatro controles,
        um por jogador) e o único em que o descarte MENTE: o mod pede o
        jogador 2 e o LED acende no 1. Rotear de verdade exigiria o mapa
        MAC->jogador, que vive no `CoopManager`, e o `UdpHandler` recebe só
        `controller` e `store`. Enquanto a fiação não existir, o descarte é
        pelo menos AUDÍTAVEL: contador + warn com o índice pedido.
        """
        if indice is None or indice == 0:
            return
        self.store.bump("udp.controller_index_ignorado")
        logger.warning("udp_controller_index_ignorado", kind=kind, index=indice)

    def _do_trigger_update(self, params: list[Any]) -> None:
        """Aceita o dialeto do Hefesto e o layout canônico do DSX."""
        if len(params) < 2:
            raise ValueError("TriggerUpdate precisa [side, mode, ...]")
        if isinstance(params[1], str):
            side_raw, mode_raw, *rest = params
            side = parse_side(side_raw)
            if side is None:
                raise ValueError(f"TriggerUpdate side invalido: {side_raw!r}")
            mode_name: str = mode_raw
        else:
            if len(params) < 3:
                raise ValueError("TriggerUpdate (DSX) precisa [idx, side, mode, ...]")
            self._nota_indice(_como_indice(params[0]), kind="TriggerUpdate")
            side = parse_side(params[1])
            if side is None:
                raise ValueError(f"TriggerUpdate side invalido: {params[1]!r}")
            mode_name, rest = resolve_dsx_trigger_mode(params[2], params[3:])
        rest_ints = [int(v) for v in rest]
        effect = build_from_name(mode_name, rest_ints)
        self.controller.set_trigger(side, effect)  # type: ignore[arg-type]

    def _do_rgb_update(self, params: list[Any]) -> None:
        if len(params) < 4:
            raise ValueError("RGBUpdate precisa [idx, r, g, b]")
        idx, r, g, b = params[:4]
        self._nota_indice(_como_indice(idx), kind="RGBUpdate")
        r_c = max(0, min(255, int(r)))
        g_c = max(0, min(255, int(g)))
        b_c = max(0, min(255, int(b)))
        self.controller.set_led((r_c, g_c, b_c))

    def _do_player_led(self, params: list[Any]) -> None:
        """Aceita `[idx, bitmask]` (Hefesto) e `[idx, b1..b5]` (DSX canônico)."""
        if len(params) >= 6:
            self._nota_indice(_como_indice(params[0]), kind="PlayerLED")
            acesos = [bool(v) for v in params[1:6]]
            mask = sum(1 << i for i, aceso in enumerate(acesos) if aceso)
        elif len(params) >= 2:
            self._nota_indice(_como_indice(params[0]), kind="PlayerLED")
            mask = int(params[1])
        else:
            raise ValueError("PlayerLED precisa [idx, bitmask] ou [idx, b1..b5]")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bool(mask & 0b00001),
            bool(mask & 0b00010),
            bool(mask & 0b00100),
            bool(mask & 0b01000),
            bool(mask & 0b10000),
        )
        self.controller.set_player_leds(bits)
        self.store.bump(f"udp.player_led.{mask}")

    def _do_mic_led(self, params: list[Any]) -> None:
        """Aceita `[state]` (Hefesto) e `[idx, MicLEDMode]` (DSX canônico)."""
        if not params:
            raise ValueError("MicLED precisa [state]")
        if len(params) >= 2:
            self._nota_indice(_como_indice(params[0]), kind="MicLED")
            modo = int(params[1])
            if modo not in DSX_MIC_LED_MODES:
                raise ValueError(f"MicLED modo DSX desconhecido: {modo}")
            state = DSX_MIC_LED_MODES[modo]
            if modo == DSX_MIC_LED_PULSE:
                # O firmware do DualSense tem o modo pulsante, mas o
                self.store.bump("udp.mic_led.pulse_degradado")
                logger.warning("udp_mic_led_pulse_degradado")
        else:
            state = bool(params[0])
        self.controller.set_mic_led(state)
        self.store.bump(f"udp.mic_led.{int(state)}")

    def _do_trigger_threshold(self, params: list[Any]) -> None:
        """Deadzone do gatilho analógico — o que a instrução significa no DSX.

        `TriggerThreshold` NÃO é um efeito háptico: no DSX ela é um corte no
        valor ANALÓGICO que o gatilho entrega ao gamepad EMULADO
        (`L2_Analog >= threshold ? L2_Analog : 0`, sem reescala). Não existe
        campo de limiar no report de saída do DualSense — o hardware não tem
        onde honrá-la —, então o único ponto fiel é a fronteira
        controle-físico → pad virtual, exatamente onde o DSX a aplica.

        Consequência que o autor do mod precisa saber: com a emulação de
        gamepad DESLIGADA (Modo Nativo, jogo lendo o controle direto) não há
        pad virtual e o limiar fica guardado sem efeito. O log `info` abaixo é
        o que torna isso auditável em vez de silencioso.
        """
        side, value, indice = parse_side_and_value(params, kind="TriggerThreshold")
        self._nota_indice(indice, kind="TriggerThreshold")
        self.store.set_udp_trigger_threshold(side, value)
        self.store.bump(f"udp.trigger_threshold.{side}.{value}")
        logger.info("udp_trigger_threshold", side=side, value=value)

    def _do_reset(self) -> None:
        """`ResetToUserSettings` do DSX — PARCIAL, e de propósito."""
        self.controller.set_trigger("left", trigger_off())
        self.controller.set_trigger("right", trigger_off())
        self.store.clear_udp_trigger_thresholds()
        self.store.bump("udp.reset_parcial")
        logger.info(
            "udp_reset_to_user_settings_parcial",
            restaurado="gatilhos, deadzone",
            nao_restaurado="cor, player-LED, mic",
        )


@dataclass
class UdpServer:
    controller: IController
    store: StateStore
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    rate_limiter: RateLimiter | None = None
    _transport: asyncio.DatagramTransport | None = None

    async def start(self) -> None:
        rate = self.rate_limiter or RateLimiter()
        handler = UdpHandler(
            controller=self.controller, store=self.store, rate_limiter=rate
        )
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: DsxProtocol(handler),
            local_addr=(self.host, self.port),
        )
        logger.info("udp_server_listening", host=self.host, port=self.port)

    async def stop(self) -> None:
        if self._transport is not None:
            with contextlib.suppress(Exception):
                self._transport.close()
            self._transport = None


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DSX_CANNED_TRIGGER_MODES",
    "DSX_CUSTOM_VALUE_MODES",
    "DSX_INSTRUCTION_TYPES",
    "DSX_MIC_LED_MODES",
    "DSX_TRIGGER_MODES",
    "DSX_TRIGGER_SIDES",
    "MAX_DATAGRAM_BYTES",
    "RATE_GLOBAL",
    "RATE_PER_IP",
    "SUPPORTED_VERSION",
    "RateLimiter",
    "UdpHandler",
    "UdpServer",
    "parse_side",
    "parse_side_and_value",
    "resolve_dsx_trigger_mode",
    "resolve_instruction_type",
]
