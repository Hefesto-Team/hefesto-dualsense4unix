"""UDP server compatível com o protocolo DSX (V2 5.10, ADR-003, V3-1).

Escuta em `127.0.0.1:6969` (configurável), parseia envelope JSON com
`version: 1` + `instructions[]`, aplica cada instrução no controle.

Fora de escopo aqui: persistir estado (fica no StateStore via handlers).
Rate limit (V3-1) roda no dispatch, global + per-IP com sweep periódico.

Schema resumido:

    { "version": 1,
      "instructions": [
        {"type": "TriggerUpdate", "parameters": [side, mode, p1..p7]},
        {"type": "RGBUpdate", "parameters": [idx, r, g, b]},
        {"type": "PlayerLED", "parameters": [idx, bitmask]},
        {"type": "MicLED", "parameters": [state]},
        {"type": "TriggerThreshold", "parameters": [side, value]},
        {"type": "ResetToUserSettings", "parameters": []}
      ]
    }

`version != 1` dropa com `log.warn` (V2 5.10).

Dois dialetos na mesma porta
----------------------------
O DSX real (Paliverse, e os mods compilados contra o SDK dele) fala um
envelope DIFERENTE deste: sem campo `version`, `type` como ORDINAL do enum
`InstructionType`, e `parameters[0]` sempre o `controllerIndex`. O daemon
aceita os DOIS, decidindo por conteúdo e nunca por adivinhação:

- `version` ausente  -> envelope do DSX (`Packet.cs` do SDK não tem o campo).
- `type` inteiro     -> resolvido por `DSX_INSTRUCTION_TYPES`.
- layout de params   -> desambiguado por tipo/aridade em cada handler.

Ordinal ou layout que NÃO dá para resolver com certeza falha alto
(`udp.unknown_instruction` / `udp.error.*` + log) em vez de agir por
aproximação: no ecossistema do DSX existe divergência real de enum entre
forks, e agir errado em silêncio é pior do que recusar.

O que continua sem cobertura está em `docs/protocol/udp-schema.md`
(seção "Fidelidade ao DSX original"), sem eufemismo.
"""
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

#: Ordinais do enum `Trigger` do DSX (`Invalid=0, Left=1, Right=2`). Mods C#
#: serializam o enum como int, então é isso que chega no fio.
DSX_TRIGGER_SIDES = {1: "left", 2: "right"}

#: Ordinais do enum `InstructionType` do DSX -> nome usado internamente.
#:
#: PROCEDÊNCIA E DIVERGÊNCIA (importante, não apagar): o enum do DSX **não é
#: único no ecossistema**. Quatro fontes públicas foram conferidas:
#:
#:   - `dvize/TarkovDSX` `DSX/InstructionType.cs` .... TriggerThreshold = 4
#:   - `WujekFoliarz/DualSenseY-v2` `include/udp.hpp`  TriggerThreshold = 4
#:   - `cosmii02/ForzaDSXlegacy` `Program.cs` ........ TriggerThreshold = 4
#:   - `cosmii02/RacingDSX` `Program.cs` ............. TriggerThreshold = 6 (!)
#:
#: O RacingDSX troca `TriggerThreshold` e `PlayerLEDNewRevision` de lugar. Vale
#: a maioria de 3 contra 1 — e o desempate real é que o DualSenseY-v2 é um
#: SERVIDOR: ele precisa casar com o que os mods de verdade emitem, senão não
#: funcionaria para os usuários dele.
#:
#: Os ordinais 1, 2, 3, 5 e 7 são unânimes nas fontes que os definem. O 4 segue
#: a maioria. O 6 (`PlayerLEDNewRevision`) e o 0 (`Invalid`/`GetDSXStatus`)
#: ficam DE FORA de propósito: nenhum deles tem instrução correspondente aqui,
#: então caem em `udp.unknown_instruction` com log — falha barulhenta, que é o
#: pior caso aceitável. Um mod do dialeto RacingDSX que mande 6 querendo dizer
#: TriggerThreshold vai falhar de forma VISÍVEL em vez de mexer no LED errado.
DSX_INSTRUCTION_TYPES: dict[int, str] = {
    1: "TriggerUpdate",
    2: "RGBUpdate",
    3: "PlayerLED",
    4: "TriggerThreshold",
    5: "MicLED",
    7: "ResetToUserSettings",
}

#: Ordinais do enum `TriggerMode` do DSX -> preset equivalente do Hefesto.
#:
#: Só entram aqui os modos em que o preset do Hefesto tem a MESMA assinatura de
#: parâmetros que o helper C# do DSX (conferido em `DSX/Instruction.cs`):
#: `Resistance(start, force)`, `Bow(start, end, force, snapForce)`,
#: `Galloping(start, end, firstFoot, secondFoot, frequency)`,
#: `SemiAutomaticGun(start, end, force)`, `AutomaticGun(start, strength,
#: frequency)` e `Machine(start, end, strengthA, strengthB, frequency, period)`.
#: Os ordinais 20-26 são a extensão do DualSenseY-v2 e usam nomes que são
#: literalmente os presets do Hefesto.
#:
#: `Normal` (0) vira `Off`: nas duas pontas significa "gatilho sem efeito".
#: NÃO é transcrição de bytes — é o preset do próprio Hefesto sendo reusado,
#: exatamente como a GUI e os perfis já o usam.
DSX_TRIGGER_MODES: dict[int, str] = {
    0: "Off",  # Normal
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

#: Ordinal do `TriggerMode.CustomTriggerValue` — tratado à parte porque o
#: primeiro parâmetro dele é outro enum (ver `DSX_CUSTOM_VALUE_MODES`).
DSX_TRIGGER_MODE_CUSTOM_VALUE = 12

#: Modos "prontos" do DSX que NÃO são implementáveis aqui, com o nome para o
#: erro sair legível. Cada um é uma CURVA DE FORÇA fechada, definida por uma
#: tabela de bytes interna do DSX — não por parâmetros que o mod mande.
#:
#: Por que não estão implementados, sem eufemismo: a única transcrição pública
#: dessas tabelas que encontrei está no `DualSenseY-v2`, que é um repositório
#: **sem licença nenhuma** (`license: null` na API do GitHub, sem arquivo
#: LICENSE) — ou seja, todos os direitos reservados. Copiar as tabelas de lá
#: para um projeto empacotado e distribuído seria problema de licença, não de
#: engenharia. Implementá-las com fidelidade exige documentação oficial da
#: Paliverse ou medir os bytes do DSX rodando. Até lá o pedido falha alto.
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

#: Enum `CustomTriggerValueMode` do DSX -> modo HID do Hefesto
#: (`core.trigger_effects.TriggerMode`). Os bits são os mesmos dos dois lados —
#: nada é transcrito, só correlacionado pelo nome.
#:
#: Os modos 9-16 (variantes *VibrateResistance*/*VibratePulse*) ficam de fora:
#: o Hefesto não tem os modos HID correspondentes, e escolher "o mais parecido"
#: mudaria a sensação no gatilho sem o mod saber.
DSX_CUSTOM_VALUE_MODES: dict[int, int] = {
    0: 0x00,  # Off
    1: 0x01,  # Rigid
    2: 0x01 | 0x20,  # RigidA
    3: 0x01 | 0x04,  # RigidB
    4: 0x01 | 0x20 | 0x04,  # RigidAB
    5: 0x02,  # Pulse
    6: 0x02 | 0x20,  # PulseA
    7: 0x02 | 0x04,  # PulseB
    8: 0x02 | 0x20 | 0x04,  # PulseAB
}

#: Enum `MicLEDMode` do DSX -> `muted` do `IController.set_mic_led`.
#: `On=0` acende o LED (convenção do firmware: aceso = mic mudo), `Off=2` apaga.
#: `Pulse=1` não existe no Hefesto e é DEGRADADO para aceso — com contador e
#: log próprios, para não passar por implementado.
DSX_MIC_LED_MODES: dict[int, bool] = {0: True, 1: True, 2: False}
DSX_MIC_LED_PULSE = 1


def resolve_instruction_type(raw: object) -> str | None:
    """Nome canônico da instrução a partir de `type`. `None` = irreconhecível.

    Aceita a string do dialeto do Hefesto (`"TriggerUpdate"`) e o ordinal do
    enum `InstructionType` do DSX, que é como o `Newtonsoft.Json` serializa um
    enum C# por padrão — e portanto o que os mods reais emitem.
    """
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
    """Traduz `(TriggerMode do DSX, params)` para `(preset do Hefesto, params)`.

    Levanta `ValueError` — nunca aproxima — quando o modo não tem equivalente
    fiel. O texto do erro nomeia o modo para o autor do mod saber o que caiu.
    """
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
        # `Custom` do Hefesto quer [modo, f0..f6]; o DSX manda até 7 forcas.
        # Completar com zero é o mesmo que o servidor do DSX faz (`getOrZero`).
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
            "é uma curva de força fechada do DSX, sem parâmetros e sem tabela "
            "de bytes publicada sob licença utilizável"
        )
    raise ValueError(f"TriggerUpdate modo DSX desconhecido: {ordinal}")


def parse_side(raw: object) -> str | None:
    """Traduz o lado do gatilho nos dois dialetos aceitos. `None` = inválido.

    Aceita ``"left"``/``"right"`` (dialeto documentado do Hefesto) e o
    ordinal do enum `Trigger` do DSX (1/2), inclusive quando o cliente o
    manda como string numérica.
    """
    if isinstance(raw, str):
        texto = raw.strip().lower()
        if texto in ("left", "right"):
            return texto
        if texto.isdigit():
            return DSX_TRIGGER_SIDES.get(int(texto))
        return None
    # `bool` é subclasse de `int`: True viraria "left" por acidente.
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return DSX_TRIGGER_SIDES.get(raw)
    return None


def parse_side_and_value(
    params: list[Any], *, kind: str
) -> tuple[str, int, int | None]:
    """Extrai `(lado, valor, índice)` dos dois layouts que chegam na 6969.

    - Dialeto do Hefesto: ``[side, value]`` — índice devolvido como `None`.
    - Layout canônico do DSX: ``[controllerIndex, side, value]``.

    A escolha é por conteúdo, não por tamanho: com 3+ parâmetros tentamos
    primeiro o layout do DSX e só caímos no dialeto textual se `params[1]`
    não for um lado válido. Assim `["left", 128]` e `[0, 1, 128]` significam
    a mesma coisa sem ambiguidade.
    """
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
    """Dois limites sobrepostos: global + per-IP (V3-1).

    IPs inativos são evictados via `_sweep` periódico (máx 1x/s).
    """

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
        # Em Python 3.10 o objeto real é `_SelectorDatagramTransport`, que
        # formalmente herda de `asyncio.DatagramTransport` mas falha no
        # `isinstance` contra a classe pública exposta no namespace. O
        # contrato do asyncio já garante o tipo via API de
        # `create_datagram_endpoint`; atribuição direta evita o ruído de
        # AssertionError no journal a cada startup (BUG-UDP-01 / A-02).
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

        # O envelope do DSX canônico NÃO tem campo `version` (ver `Packet.cs`
        # do SDK: a classe só carrega `Instruction[] instructions`). Ausência
        # portanto significa "protocolo DSX", não "pacote malformado" — era
        # aqui que TODO mod real morria, antes de qualquer instrução ser lida.
        # Um `version` PRESENTE e diferente de 1 continua sendo descarte.
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
        # `type` chega como string (dialeto do Hefesto) ou como ordinal do enum
        # `InstructionType` (DSX canônico — é assim que o Newtonsoft serializa
        # um enum C#). `None` só para tipo de dado impossível.
        kind = resolve_instruction_type(raw_kind)
        if kind is None:
            if isinstance(raw_kind, int):
                # Ordinal fora da tabela: pode ser `PlayerLEDNewRevision`, um
                # `GetDSXStatus`, ou o dialeto divergente do RacingDSX. Nenhum
                # tem ação aqui — barulhento é melhor do que agir errado.
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
        """Aceita o dialeto do Hefesto e o layout canônico do DSX.

        A desambiguação é pelo TIPO de `params[1]`: no dialeto do Hefesto ele
        é o nome do preset (string), no DSX é o ordinal do lado (int). Não há
        sobreposição possível entre os dois.
        """
        if len(params) < 2:
            raise ValueError("TriggerUpdate precisa [side, mode, ...]")
        if isinstance(params[1], str):
            side_raw, mode_raw, *rest = params
            side = parse_side(side_raw)
            if side is None:
                raise ValueError(f"TriggerUpdate side invalido: {side_raw!r}")
            mode_name: str = mode_raw
        else:
            # [controllerIndex, side, mode, p1..pN]
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
        # Clamp silencioso em [0, 255] para compatibilidade com clients DSX
        # imprecisos. Alinha comportamento ao handler IPC `led.set` que valida
        # range (achado 19 da auditoria forense V23).
        r_c = max(0, min(255, int(r)))
        g_c = max(0, min(255, int(g)))
        b_c = max(0, min(255, int(b)))
        self.controller.set_led((r_c, g_c, b_c))

    def _do_player_led(self, params: list[Any]) -> None:
        """Aceita `[idx, bitmask]` (Hefesto) e `[idx, b1..b5]` (DSX canônico).

        Desambiguação por aridade: o helper `Instruction.PlayerLED` do DSX
        manda SEMPRE seis parâmetros (índice + cinco booleanos), então 6+ é
        o layout do DSX e 2 é o bitmask. Bit i / booleano i = LED i (bit 0 =
        LED da esquerda).
        """
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
        """Aceita `[state]` (Hefesto) e `[idx, MicLEDMode]` (DSX canônico).

        Desambiguação por aridade: o helper `Instruction.MicLED` do DSX manda
        dois parâmetros; o dialeto daqui manda um.
        """
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
                # `IController` só expõe aceso/apagado. Acender é o mais perto
                # — e o contador+log impedem que isso passe por implementado.
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
        """`ResetToUserSettings` do DSX — PARCIAL, e de propósito.

        Desliga os dois gatilhos e apaga a deadzone que um mod tenha pedido
        por `TriggerThreshold` (as duas coisas que a porta 6969 sabe desfazer
        sozinha). NÃO restaura cor/LED de player/mic do perfil ativo: o
        `UdpHandler` recebe só `controller` e `store`, não o gerenciador de
        perfis, e reaplicar perfil a partir daqui seria inventar um caminho
        de escrita de perfil paralelo aos que já têm dono. Está documentado
        como parcial em `docs/protocol/udp-schema.md`.
        """
        self.controller.set_trigger("left", trigger_off())
        self.controller.set_trigger("right", trigger_off())
        self.store.clear_udp_trigger_thresholds()
        # O nome da instrução promete mais do que esta implementação entrega.
        # Como o nome é do protocolo e não nosso, o que dá para fazer é não
        # deixar a diferença invisível: o log diz o que voltou e o que não.
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
