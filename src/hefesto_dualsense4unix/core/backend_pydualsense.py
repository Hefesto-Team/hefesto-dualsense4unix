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
    a TODOS os controles (fan-out) e o "perfil ativo" é cacheado como estado
    desejado POR CONTROLE (PERFIL-01/4P-01: `_desired_default` broadcast +
    `_desired_by_uniq` keyed por MAC) para ser re-aplicado — com MERGE POR
    CAMPO — a um controle plugado em runtime (hotplug-in).
  - INPUT/EMULAÇÃO permanece SÓ no controle PRIMÁRIO (o evdev e o `read_state`
    seguem single-instance; o `_ds` aponta para o primário). 100% compatível
    com o caso de 1 controle.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydualsense import pydualsense

from hefesto_dualsense4unix.core.controller import (
    ControllerState,
    IController,
    OutputSpec,
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
    from collections.abc import Callable, Mapping

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: PID do DualSense Edge (os demais PIDs em `DUALSENSE_PIDS` são o DualSense
#: comum). Usado para sinalizar `is_edge` ao abrir o handle.
DUALSENSE_EDGE_PID = 0x0DF2

#: STATUS-01 (priming): azul-default que o `hid_playstation` acende no probe
#: por um caminho interno que NUNCA atualiza a classe LED (`dualsense_create`
#: → `dualsense_set_lightbar`, provado no kernel upstream). Escrever ESTE RGB
#: via sysfs num nó recém-surgido é idempotente com o hardware (a lightbar já
#: está azul) e serve só para a classe LED convergir com a realidade — sem
#: isso, todo reconnect BT/hotplug leria `0 0 0` com o LED visivelmente aceso.
KERNEL_DEFAULT_BLUE: tuple[int, int, int] = (0, 0, 128)

#: REPLICA-03: tamanho do bloco de trigger effect que o jogo escreve no report
#: 0x02 do vpad (modo + 10 parâmetros — `rgucRightTriggerEffect[11]` do
#: DS5EffectsState_t do SDL; no kernel a área é o `reserved2` do
#: `dualsense_output_report_common`, common[10..20]/[21..31]).
GAME_TRIGGER_BLOCK_LEN = 11

#: NUMA-03: intervalo mínimo entre duas defesas de exibição disparadas por
#: réplica RETIDA (`defend_display` via `set_game_output_for` sob autoridade
#: 'daemon'). Réplica retida = prova de escritor ativo, mas a defesa reescreve
#: sysfs em todos os nós — sem o teto ela viraria o reassert incondicional que
#: causou o flash azul de 30s (GUERRA-01). A defesa por TRANSIÇÃO (*→daemon)
#: não passa por este teto: já é rate-limitada pela histerese de 30s do sinal.
DEFEND_DISPLAY_MIN_INTERVAL_S = 30.0

#: GYRO-01: feature report da calibração da IMU (`DS_FEATURE_REPORT_CALIBRATION`
#: / `_SIZE` do hid-playstation.c). Lido POR UNIDADE em `read_calibration` para
#: o vpad carimbar no blueprint — por BT os 4 últimos bytes são CRC-32 (seed
#: 0xA3) e são validados antes de aceitar.
_CALIBRATION_FEATURE_ID = 0x05
_CALIBRATION_FEATURE_SIZE = 41


def _read_feature_via_hidraw(path: str, report_id: int, size: int) -> bytes:
    """GET_REPORT de feature via HIDIOCGFEATURE num fd efêmero (GYRO-01).

    Espelho do `_hidiocgfeature` de `uhid_gamepad.py` (caminho VALIDADO ao
    vivo pelo capture do blueprint) — duplicado aqui porque core/ não importa
    integrations/. Devolve o report como o kernel o entrega: ``data[0]`` é o
    report id e o payload começa em ``data[1]`` (`hidraw_get_report` +
    `hid_hw_raw_request`). Propaga OSError (EIO do BT ocioso, permissão) para
    o chamador decidir o fallback.
    """
    fd = os.open(path, os.O_RDWR)
    try:
        buf = bytearray(size)
        buf[0] = report_id
        # HIDIOCGFEATURE(len) = _IOC(READ|WRITE, 'H', 0x07, len)
        request = (3 << 30) | (size << 16) | (ord("H") << 8) | 0x07
        ret = fcntl.ioctl(fd, request, buf, True)
        return bytes(buf[:ret]) if ret > 0 else b""
    finally:
        os.close(fd)


#: Identidade do vpad no HID: phys gravado pelo blueprint (uhid_gamepad) e
#: prefixo do MAC forjado (`player_mac()` → 02:fe:00:00:00:0N).
_VPAD_PHYS = "hefesto-vpad"
_VPAD_UNIQ_PREFIX = "02fe"


def _hidraw_uevent(node: str) -> dict[str, str]:
    """Pares chave=valor do uevent do device HID pai do hidraw ({} se ilegível)."""
    try:
        with open(
            f"/sys/class/hidraw/{node}/device/uevent",
            encoding="utf-8",
            errors="replace",
        ) as fh:
            raw = fh.read()
    except OSError:
        return {}
    pares: dict[str, str] = {}
    for linha in raw.splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            pares[chave] = valor
    return pares


def _is_virtual_hidraw(path: bytes) -> bool:
    """True se o hidraw é do NOSSO vpad uhid, não de controle físico.

    Espelha o `_is_virtual_evdev` do `evdev_reader` — e pela mesma razão CRÍTICA:
    o vpad do SPRINT-UHID-VPAD-01 nasce com VID/PID/bus idênticos ao controle
    real (é o que faz o `hid_playstation` fazer bind nele) e, ao contrário do
    vpad de uinput, tem **hidraw de verdade**. Sem este filtro o daemon adota o
    PRÓPRIO vpad como se fosse mais um controle físico — feedback loop (o daemon
    lendo a própria saída) e "3 controles" com dois na mesa.

    Medido ao vivo antes do filtro: com o vpad no ar, o enumerate devolvia
    ``('02:fe:00:00:00:02', b'/dev/hidraw7', False)`` — o MAC que nós forjamos.

    BLUEZ-UHID-01 (2026-07-19): morar sob `/sys/devices/virtual/misc/uhid/`
    DEIXOU de implicar "nosso vpad" — com BlueZ ≥5.73 (UserspaceHID default) o
    bluetoothd cria os HIDs dos controles BT FÍSICOS via /dev/uhid, no mesmo
    subtree. Medido ao vivo com o backport 5.85: os 4 controles BT da mesa
    ficaram invisíveis ao daemon (`connected: False` com 4 hidraws saudáveis).
    O critério agora é a IDENTIDADE do vpad no uevent do pai HID — HID_PHYS
    `hefesto-vpad` (blueprint) ou HID_UNIQ com prefixo 02:fe — alinhado à regra
    do projeto de validar pelo uevent do pai HID imediato, nunca por topologia.
    uevent ilegível sob o subtree virtual → True: na dúvida, o risco maior é o
    feedback loop de auto-adoção (o retry do reconcile cobre o falso-positivo).
    """
    node = os.path.basename(path.decode("utf-8", "replace"))
    if not node.startswith("hidraw"):  # path de libusb ("0001:0002:00")
        return False
    try:
        destino = os.path.realpath(f"/sys/class/hidraw/{node}/device")
    except OSError:  # pragma: no cover - sysfs some sob replug
        return False
    if "/devices/virtual/" not in destino:
        return False
    uevent = _hidraw_uevent(node)
    if not uevent:
        return True
    phys = uevent.get("HID_PHYS", "")
    uniq = uevent.get("HID_UNIQ", "").lower().replace(":", "")
    return phys == _VPAD_PHYS or uniq.startswith(_VPAD_UNIQ_PREFIX)

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

#: Teto do throttle adaptativo por-controle (PERF-MULTI-CONTROLLER-01): com N
#: controles o throttle vira `base * N` capado aqui — 2 controles ≈ 60Hz de
#: output, 4 ≈ 30Hz. Output é LED/trigger/rumble (latência de até ~32ms é
#: imperceptível); o INPUT vem do evdev e não passa por este ciclo.
REPORT_THREAD_THROTTLE_MAX_SEC: float = 0.032

#: Keepalive do write OUT quando o report não mudou (PERF-MULTI-CONTROLLER-01):
#: o firmware retém o último estado, então reescrever um report IDÊNTICO a
#: ~100Hz só satura o barramento (2+ controles = pressão no host controller da
#: família do storm). Reescrevemos no máximo a cada 0.5s quando nada mudou —
#: cobre perda de report e glitch de link sem martelar o USB.
OUT_REPORT_KEEPALIVE_SEC: float = 0.5


@dataclass
class _DesiredOutput:
    """Último output aplicado = "perfil ativo" materializado em HID.

    PERFIL-01 (4P-01): existe um `_desired_default` (padrão broadcast) e um
    override PARCIAL por controle em `_desired_by_uniq` (keyed pelo MAC
    12-hex, estável entre USB e BT — provado ao vivo). O hotplug-in re-aplica
    o MERGE POR CAMPO dos dois no controle CERTO — nunca o de outro (era o
    bug provado: mirar o Controle 2 no seletor e replugar o Controle 1 o
    pintava com a cor do 2). O rumble é transitório (efeito de jogo, não faz
    parte de um perfil) e por isso NÃO entra aqui — não seria correto
    "ressuscitar" um rumble antigo num controle novo.
    """

    trigger_left: TriggerEffect | None = None
    trigger_right: TriggerEffect | None = None
    led: tuple[int, int, int] | None = None
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None
    mic_led: bool | None = None


#: Campos de `_DesiredOutput`/`OutputSpec` — a ordem é a de aplicação no HID.
_OUTPUT_FIELDS = ("trigger_left", "trigger_right", "led", "player_leds", "mic_led")


def _spec_fields(spec: OutputSpec) -> dict[str, Any]:
    """Campos NÃO-None de um `OutputSpec` (o vocabulário parcial do PERFIL-01)."""
    return {
        name: getattr(spec, name)
        for name in _OUTPUT_FIELDS
        if getattr(spec, name) is not None
    }


def _merge_desired(default: _DesiredOutput, override: _DesiredOutput | None) -> _DesiredOutput:
    """MERGE POR CAMPO (PERFIL-01): campo do override quando não-None, senão o default.

    NUNCA resolução por objeto (refutada na revisão adversarial do sprint):
    um override PARCIAL (só gatilhos) precisa herdar a cor global do perfil —
    resolver por objeto aplicaria `led=None` como no-op e o controle replugado
    ficaria sem a cor broadcast.
    """
    if override is None:
        return default
    return _DesiredOutput(
        **{
            name: (
                getattr(override, name)
                if getattr(override, name) is not None
                else getattr(default, name)
            )
            for name in _OUTPUT_FIELDS
        }
    )


def _centered_stick_to_raw(value: Any) -> int:
    """Converte um eixo de stick da pydualsense (centrado em 0) para cru 0-255.

    FEAT-MOUSE-CURSOR-FEEL-01 (A6): a pydualsense 0.7.5 instalada armazena
    ``state.LX = states[1] - 128`` (range -128..127, repouso = 0). O fallback
    HID-raw fazia ``int(state.LX) & 0xFF``, que transformava repouso (cru 128 →
    LX=0) em raw 0 e drift leve (cru 125 → LX=-3) em raw 253 — o cursor "voava"
    na diagonal com o stick parado (é a memória "sticks ~253 em repouso").
    Somar 128 de volta e clampar restaura o valor cru que o resto do pipeline
    (deadzone em 128, gamepad virtual, check de neutralidade) espera.
    """
    return max(0, min(255, int(value) + 128))


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
        # FEAT-DSX-LIGHTBAR-SYSFS-01: quando a lightbar/player-LED deste controle
        # estão sendo controlados pela rota sysfs do kernel (cor funciona em
        # USB E BT), suprimimos a escrita desses LEDs no report_thread para NÃO
        # disputar com o kernel (a disputa é o que faz a cor "não colar" no BT).
        # `_refresh_sysfs_leds` mantém True SÓ quando o sysfs é gravável; senão
        # vira False e o caminho pydualsense segue normal.
        #
        # LIGHTBAR-BT-ADOPT-01 (provado ao vivo 2026-07-18; estudo 5 agentes):
        # nasce TRUE, nunca False. O report_thread começa a escrever assim que o
        # handle abre — ANTES de `_refresh_sysfs_leds` rodar. Nascendo False, o
        # 1º report saía com os flags de lightbar/player LIGADOS — e o report BT
        # da pydualsense 0.7.5 é MALFORMADO (layout off-by-one: [1]=0x02 fixo,
        # 0xFF onde o firmware espera o tag obrigatório 0x10, campos deslocados
        # 1 byte). Chegando dentro da JANELA da máquina de estados da lightbar
        # do firmware (~3.4s pós-connect BT — o SDL espera essa janela e fecha
        # com flag1 0x08 "Reset LED state"; o kernel nunca envia 0x08), a
        # lightbar LATCHEIA APAGADA e passa a ignorar as escritas de cor do
        # kernel (330k writes em multi_intensity sem acender, provado ao vivo) —
        # enquanto player-LEDs/gatilhos, sem máquina de estados própria, seguem
        # funcionando. O latch persiste até o POWER-OFF do controle (sobrevive a
        # re-parear e a rebind do driver; cabo USB escapa — report 0x02 sem
        # seq/janela). Sintoma: a lightbar acende no connect e APAGA na adoção.
        # Nascer suprimido fecha a janela inteira (inclusive o zumbi do
        # init-timeout, que nenhum refresh alcança); quem decide o estado final
        # continua sendo `_refresh_sysfs_leds` (~ms depois, no próprio connect).
        self._suppress_leds = True
        # PERF-MULTI-CONTROLLER-01: throttle POR-INSTÂNCIA (o backend escala
        # com o nº de controles conectados) + dirty-flag do write OUT.
        self._throttle_sec = REPORT_THREAD_THROTTLE_SEC
        self._last_out_report: list[int] | None = None
        self._last_write_at = 0.0
        # FEAT-NATIVE-OUTPUT-MUTE-01: em Modo Nativo o JOGO escreve no hidraw
        # (rumble/gatilhos/LED nativos); QUALQUER write nosso — até o keepalive
        # de 0.5s — pisoteia o que o jogo mandou (rumble zerado a cada meio
        # segundo, sentido ao vivo no Sackboy 2026-07-13). Mutado = zero write;
        # a leitura de input/bateria continua.
        self._output_muted = False
        # GUERRA-01 item 2 (keepalive neutro): com o upstream, TODO report sai
        # com os bits de vibração do flag0 ligados (0xFF) e motores=0 — o
        # keepalive zerava rumble de TERCEIROS (o jogo escrevendo direto no
        # hidraw do físico) a cada ≤0.5s. Agora os bits de vibração só ligam
        # quando há rumble NOSSO ativo (`_rumble_active`) ou na transição
        # ativa→0 (`_rumble_stop_pending`: UM report com flags ligados e
        # motores 0 para parar o motor de verdade; depois volta ao neutro).
        self._rumble_active = False
        self._rumble_stop_pending = False
        # BTREPORT-02: contador de sequência do report 0x31 (wrap 0-15, como o
        # hid_playstation faz), carimbado por `writeReport` no momento do
        # write — nunca no prepare, senão todo report "mudaria" e o dedup
        # `_last_out_report` morreria (write a ~125Hz de volta).
        self._bt_seq = 0
        # REPLICA-03: blocos CRUS de trigger effect do JOGO (11 bytes: modo +
        # 10 parâmetros, layout do DS5EffectsState_t do SDL). Quando setados,
        # `_build_common` os embute VERBATIM em common[10..20]/[21..31] no
        # lugar do estado da pydualsense — a DSTrigger só representa 7 forças
        # e espalharia zeros nos parâmetros 8/9/10 do efeito do jogo. None =
        # posse do perfil (caminho DSTrigger histórico).
        self._raw_trigger_right: bytes | None = None
        self._raw_trigger_left: bytes | None = None

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
                # FEAT-NATIVE-OUTPUT-MUTE-01: mutado (Modo Nativo) = NENHUM
                # write; o jogo é o dono do output deste controle.
                if not self._output_muted:
                    out = self.prepareReport()
                    now = time.monotonic()
                    # PERF-MULTI-CONTROLLER-01: write OUT só quando o report
                    # MUDOU, com keepalive esparso. O seq-tag BT da pydualsense
                    # é fixo, e o report USB não tem contador — o buffer é
                    # função pura do estado desejado, então a comparação detecta
                    # mudança real (rumble do jogo, trigger novo, LED). Report
                    # idêntico reescrito a ~100Hz era pura pressão de barramento
                    # com 2+ controles.
                    if (
                        out != self._last_out_report
                        or (now - self._last_write_at) >= OUT_REPORT_KEEPALIVE_SEC
                    ):
                        self.writeReport(out)
                        self._last_out_report = out
                        self._last_write_at = now
                throttle = self._throttle_sec
                if throttle > 0:
                    time.sleep(throttle)
            except OSError:
                self.connected = False
                break
            except AttributeError:
                self.connected = False
                break

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setLeftMotor(intensity)
        self._track_rumble_transition()

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setRightMotor(intensity)
        self._track_rumble_transition()

    def _track_rumble_transition(self) -> None:
        """GUERRA-01 item 2: rastreia rumble NOSSO ativo e a transição ativa→0.

        `_rumble_active` liga com qualquer motor > 0; ao ambos zerarem, vira
        `_rumble_stop_pending` — o próximo report sai com os flags de vibração
        LIGADOS (e motores 0) para o firmware parar o motor de verdade, e só
        então o report volta ao neutro. 0→0 não gera stop (nunca vibrou).
        """
        active = bool(self.leftMotor or self.rightMotor)
        if active:
            self._rumble_active = True
        elif self._rumble_active:
            self._rumble_active = False
            self._rumble_stop_pending = True

    def _build_common(self, *, rumble_asserted: bool) -> bytearray:
        """Payload "common" (47 bytes) a partir do estado da pydualsense.

        Mesmo mapeamento de campos do upstream (motores, mic, gatilhos, LED),
        mas com DUAS políticas nossas aplicadas na origem:

        - keepalive neutro (GUERRA-01 item 2): sem rumble nosso ativo, os bits
          de vibração (flag0 0x01|0x02, atenuação 0x40 do flag1 e a vibração
          v2 0x04 do flag2) saem DESLIGADOS — o firmware mantém o estado
          anterior e o rumble de terceiros sobrevive ao nosso keepalive;
        - supressão de LED (FEAT-DSX-LIGHTBAR-SYSFS-01): `_suppress_leds`
          limpa lightbar 0x04 + player 0x10 do flag1 (o kernel é o dono).
        """
        from hefesto_dualsense4unix.core import ds_output_report as rep

        common = bytearray(rep.COMMON_LEN)
        flag0 = 0xFF  # upstream: vibração+gatilhos+áudio sempre autorizados
        flag1 = 0x01 | 0x02 | 0x04 | 0x10 | 0x40  # upstream: mic+LED+atenuação
        flag2 = int(self.light.ledOption.value)
        if not rumble_asserted:
            flag0 &= ~(
                rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT
            )
            flag1 &= ~rep.VALID_FLAG1_MOTOR_POWER
            flag2 &= ~rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
        if getattr(self, "_suppress_leds", False):
            flag1 &= ~(
                rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
                | rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
            )
        common[0] = flag0
        common[1] = flag1
        common[2] = int(self.rightMotor) & 0xFF
        common[3] = int(self.leftMotor) & 0xFF
        common[8] = int(self.audio.microphone_led) & 0xFF
        common[9] = 0x10 if self.audio.microphone_mute else 0x00
        # REPLICA-03: bloco cru do jogo (se em posse) vence o estado DSTrigger.
        raw_r = getattr(self, "_raw_trigger_right", None)
        if raw_r is not None and len(raw_r) == GAME_TRIGGER_BLOCK_LEN:
            common[10 : 10 + GAME_TRIGGER_BLOCK_LEN] = raw_r
        else:
            common[10] = int(self.triggerR.mode.value) & 0xFF
            for i in range(6):
                common[11 + i] = int(self.triggerR.forces[i]) & 0xFF
            common[19] = int(self.triggerR.forces[6]) & 0xFF
        raw_l = getattr(self, "_raw_trigger_left", None)
        if raw_l is not None and len(raw_l) == GAME_TRIGGER_BLOCK_LEN:
            common[21 : 21 + GAME_TRIGGER_BLOCK_LEN] = raw_l
        else:
            common[21] = int(self.triggerL.mode.value) & 0xFF
            for i in range(6):
                common[22 + i] = int(self.triggerL.forces[i]) & 0xFF
            common[30] = int(self.triggerL.forces[6]) & 0xFF
        common[rep.COMMON_VALID_FLAG2] = flag2
        common[41] = int(self.light.pulseOptions.value) & 0xFF
        common[42] = int(self.light.brightness.value) & 0xFF
        common[43] = int(self.light.playerNumber.value) & 0xFF
        common[44] = int(self.light.TouchpadColor[0]) & 0xFF
        common[45] = int(self.light.TouchpadColor[1]) & 0xFF
        common[46] = int(self.light.TouchpadColor[2]) & 0xFF
        return common

    def prepareReport(self) -> list[int]:  # noqa: N802 - override do nome do upstream
        """Monta o report pelo builder comum (BTREPORT-02) — não usa o upstream.

        USB: envelope 0x02 (idêntico ao histórico). BT: envelope 0x31 CORRETO
        (`[1]=seq<<4`, `[2]=0x10`, common em `[3..49]`, CRC nos 4 últimos) —
        o 0x31 da pydualsense 0.7.5 é malformado e o firmware o descarta, o
        que fazia todo o nosso output BT (rumble/gatilhos/keepalive) ser
        no-op. O nibble de seq sai 0 aqui (report comparável para o dedup
        `_last_out_report`); quem carimba o contador real é `writeReport`.

        Fallback: qualquer falha na montagem cai no report do upstream (USB
        correto; BT malformado = comportamento pré-fix, nunca pior) — o
        report_thread não pode morrer por causa disto.
        """
        try:
            from pydualsense.enums import ConnectionType

            from hefesto_dualsense4unix.core import ds_output_report as rep

            stop_pending = self._rumble_stop_pending
            common = self._build_common(
                rumble_asserted=self._rumble_active or stop_pending
            )
            if self.conType == ConnectionType.BT:
                report = list(rep.build_bt_report(common, seq=0))
            else:
                report = list(rep.build_usb_report(common))
            if stop_pending:
                # O report de STOP (flags ligados, motores 0) foi montado —
                # o próximo ciclo volta ao neutro. Limpa SÓ o snapshot lido
                # (um pending novo, setado durante a montagem, sobrevive).
                self._rumble_stop_pending = False
            return report
        except Exception:  # nunca derrubar o report_thread por causa disto
            fallback: list[int] = super().prepareReport()
            return fallback

    def writeReport(self, outReport: list[int]) -> None:  # noqa: N802,N803 - upstream
        """Write com carimbo de sequência BT (BTREPORT-02).

        Reports 0x31 ganham o contador por handle (wrap 0-15) + CRC recalculado
        NUMA CÓPIA — o buffer original (que `sendReport` guarda em
        `_last_out_report`) permanece com seq 0, mantendo o dedup funcional.
        """
        if len(outReport) == 78 and outReport[0] == 0x31:
            from hefesto_dualsense4unix.core import ds_output_report as rep

            stamped = list(outReport)
            rep.stamp_bt_seq(stamped, self._bt_seq)
            self._bt_seq = (self._bt_seq + 1) & 0x0F
            self.device.write(bytes(stamped))
            return
        self.device.write(bytes(outReport))


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
        # PERFIL-01 (4P-01): estado desejado POR CONTROLE. `_desired_default`
        # é o padrão broadcast (o "perfil ativo" histórico); `_desired_by_uniq`
        # guarda o override PARCIAL de cada controle, keyed pelo MAC 12-hex
        # normalizado (o mesmo `_key_to_uniq` — estável entre USB e BT). O
        # hotplug-in re-aplica o MERGE POR CAMPO dos dois no controle certo.
        self._desired_default = _DesiredOutput()
        self._desired_by_uniq: dict[str, _DesiredOutput] = {}
        # COR-03: provider da camada AUTOMÁTICA do desejado (cor do slot +
        # player-LED do número do controle), injetado pelo daemon via
        # `set_auto_output_provider` (injeção de dependência — core/ nunca
        # importa daemon/). None = sem camada automática (o merge cai no
        # comportamento histórico default+override). Consultado POR UNIQ em
        # `_merged_desired_for_key`, SOB `_io_lock` — o provider DEVE ser
        # barato e sem I/O.
        self._auto_output_provider: Callable[[str], _DesiredOutput | None] | None = None
        # REPLICA-03: camada GAME do desejado — o que o JOGO escreveu no vpad
        # deste controle (lightbar/player-LED), replicado pelo daemon. É o TOPO
        # do merge de `_merged_desired_for_key` (jogo vence override, auto e
        # default enquanto a sessão uhid estiver aberta) e some no
        # `end_game_session_for` (UHID_CLOSE), quando o perfil/paleta voltam.
        # Os trigger effects do jogo ficam à parte (`_game_triggers_by_uniq`):
        # são blocos CRUS de 11 bytes (não cabem no TriggerEffect de 7 forças)
        # aplicados direto no handle (`_raw_trigger_*`).
        self._game_output_by_uniq: dict[str, _DesiredOutput] = {}
        self._game_triggers_by_uniq: dict[str, dict[str, bytes]] = {}
        # NUMA-02: provider da AUTORIDADE de exibição ('game'|'daemon'|
        # 'unknown'), injetado pelo daemon (GameSignal do lifecycle) — leitura
        # de estado cacheado, zero I/O (mesmo contrato do
        # `_auto_output_provider`). None = sem fiação = `_game_wins()` True
        # (compat byte-idêntica: FakeController e a suíte REPLICA-03 inteira
        # não mudam de comportamento — fail-safe "nunca pior que hoje").
        self._game_authority_provider: Callable[[], str] | None = None
        # NUMA-02 (retain-latest): réplicas de EXIBIÇÃO recebidas sob
        # autoridade 'daemon' — 1 valor por (uniq, categoria), sempre o MAIS
        # recente (bounded por construção: só 'led'/'player_leds' por MAC).
        # `replay_retained_game_outputs()` entrega tudo 1x na abertura do
        # gate — a escrita ÚNICA de player-LED que jogos fazem (FATO 0) não
        # pode se perder na latência ~2s do sinal. Drop sem retenção é
        # vetado pela síntese da Onda N. Correção pós-auditoria: também
        # purgado por `end_game_session_for` no fim da MESMA sessão que o
        # gerou — sem isso, o valor sobrevive ao UHID_CLOSE (é um dict por
        # uniq, não por sessão) e vaza para a PRÓXIMA sessão de jogo real
        # deste controle via `replay_retained_game_outputs`, mesmo sem
        # nenhuma relação com quem escreveu o valor original.
        self._retained_game_outputs: dict[str, dict[str, Any]] = {}
        # Log `game_output_retido_sem_jogo` 1x por episódio (re-armado no
        # replay — episódio = um período contínuo de autoridade 'daemon').
        self._retained_log_armed = True
        # NUMA-03: monotonic da última defesa de exibição (rate-limit da
        # defesa disparada por réplica retida).
        self._defend_last_at: float | None = None
        # FEAT-DSX-LIGHTBAR-SYSFS-01: mapeia key (serial/MAC/path) -> nó LED do
        # kernel (sysfs) para os controles cuja lightbar/player-LED são graváveis
        # por sysfs. Quando presente, a cor/player vão por essa rota (USB E BT) e
        # a escrita pydualsense desses LEDs é suprimida (anti-contenção). Vazio =
        # ninguém coberto (sem regra udev / driver antigo) → caminho pydualsense.
        self._sysfs: dict[str, Any] = {}
        # STATUS-01: rastreio "escrito por nós" — key (a mesma de `_sysfs`) ->
        # última cor RGB escrita POR ESTE backend via classe LED (sysfs). É a
        # prova de POSSE do nó que autoriza ler `multi_intensity` como verdade
        # (refutação 1 do sprint: a classe nasce zerada no probe e `0 0 0` sem
        # escrita nossa NUNCA significa "apagada"). Mantido por
        # `record_sysfs_write`/`_refresh_sysfs_leds`; podado junto com o mapa.
        self._sysfs_written: dict[str, tuple[int, int, int]] = {}
        # FEAT-DSX-CONTROLLER-SELECTOR-01: ALVO das ações de output. None =
        # TODOS (broadcast, padrão e idêntico ao histórico). Guardamos a KEY
        # estável (serial/MAC) do controle escolhido — NÃO o índice — para
        # sobreviver a hotplug/troca de porta. Se a key alvo sumir (controle
        # desconectou), o `_for_each` cai de volta em broadcast.
        self._output_target_key: str | None = None
        # FEAT-NATIVE-OUTPUT-MUTE-01: espelho no backend do mute de output
        # (Modo Nativo) — aplicado a todo handle atual E aos que abrirem
        # durante o mute (hotplug com o jogo aberto).
        self._output_mute = False
        # Protege a mutação de `_handles`/`_primary_key` contra o fan-out de
        # escrita: o daemon roda `connect`/`read_state`/setters em executor
        # multi-thread (max_workers=2). RLock pois um caminho pode reentrar.
        self._io_lock = threading.RLock()
        # L2: chaves cuja abertura (`_open_one`) está EM ANDAMENTO. O
        # `reconnect_loop` (via `connect`) e o reconnect do poll loop podem
        # disparar a abertura da MESMA key em paralelo — trabalho duplicado caro
        # (até INIT_TIMEOUT_SEC por probe) cujo handle dup já era descartado.
        # Marcamos a key aqui sob `_io_lock` antes de abrir e a removemos depois,
        # para que o probe concorrente pule essa key em vez de reabrir.
        self._opening: set[str] = set()
        # HOTFIX-2: evdev como fonte primária de input (contorna conflito
        # com kernel hid_playstation). pydualsense segue como caminho de
        # output (triggers, LED, rumble). Single-instance, atrelado ao primário.
        self._evdev = evdev_reader if evdev_reader is not None else EvdevReader()
        # GYRO-01: `PhysicalReportReader` do vpad do P1 (espelho de motion),
        # registrado pelo daemon via `attach_motion_reader`. O backend só o
        # cutuca no retarget de primário (`_recompute_primary`), junto do
        # `_evdev.retarget` — quem cria/para o reader é o subsystem gamepad.
        self._motion_reader: Any | None = None

    # --- identidade ------------------------------------------------------

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        """Nó hidraw do controle `uniq` (None = primário), ou None.

        SPRINT-UHID-VPAD-01: é de onde o vpad uhid copia o report descriptor e os
        feature reports do probe (o "blueprint"). Vem do `_pinned_path` do handle
        já aberto — não re-enumera.

        Devolve None para path de libusb ("0001:0002:00"), que não é nó do sysfs
        e não serve de blueprint; o chamador cai no uinput.
        """
        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
            handle = self._handles.get(key) if key is not None else None
        path = getattr(handle, "_pinned_path", None)
        if not isinstance(path, bytes):
            return None
        texto = path.decode("utf-8", "replace")
        return texto if texto.startswith("/dev/hidraw") else None

    def _key_for_uniq(self, uniq: str) -> str | None:
        """Key do handle cujo MAC normalizado é `uniq` (None se não achar)."""
        for key in self._handles:
            if self._key_to_uniq(key) == uniq:
                return key
        return None

    def attach_motion_reader(self, reader: Any | None) -> None:
        """Registra (ou remove, com None) o reader de motion do P1 (GYRO-01).

        Injeção do daemon (`subsystems/gamepad.py`) — core/ nunca importa
        daemon/. O único uso aqui é o retarget: quando o primário troca,
        `_recompute_primary` manda o reader largar o hidraw antigo e reabrir
        no do primário novo (o `path_provider` dele re-resolve sozinho).
        """
        with self._io_lock:
            self._motion_reader = reader

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        """Feature 0x05 (calibração da IMU) do controle `uniq` (None = primário).

        GYRO-01: é o report que o vpad carimba no blueprint para o
        `hid_playstation`/SDL calibrarem o motion espelhado com o bias e a
        sensibilidade DA UNIDADE que produz os bytes crus — o canônico
        embutido veio de UMA unidade e faz as outras drivarem.

        A leitura vai por HIDIOCGFEATURE direto no hidraw do handle (o mesmo
        caminho provado do `capture_dualsense_blueprint`), NÃO pelo
        `get_feature_report` da hidapi: o wrapper pure-python instalado faz
        ``return buf[1:]`` — descarta o byte do report id e devolve
        payload+pad, o que desmolduraria o report (e a validação por id
        passaria só quando o primeiro byte de payload por acaso fosse 0x05).
        O ioctl devolve o report EXATO do kernel, id incluído — byte-compatível
        com o `CANONICAL_FEATURE_0X05` do blueprint. Fd próprio e efêmero: zero
        contenção com o read bloqueante do report_thread no handle da hidapi.

        Fail-safe por contrato: qualquer falha devolve None e o chamador fica
        no 0x05 canônico (vpad sempre nasce; drift leve tolerável). Modos de
        falha reais: BT ocioso responde EIO no GET_REPORT (timeout de 5 s do
        hidp — raro aqui, o report_thread mantém o link quente) e rádio
        corrompendo o report — por BT os 4 últimos bytes são CRC-32 (seed
        0xA3, `PS_FEATURE_CRC32_SEED` do kernel) e são VALIDADOS antes de
        aceitar: uma calibração corrompida carimbada no vpad quebraria o
        motion inteiro, não só o drift.
        """
        from hefesto_dualsense4unix.core.ds_output_report import (
            BT_FEATURE_CRC_SEED,
            bt_crc32,
        )

        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
            handle = self._handles.get(key) if key is not None else None
            if handle is None:
                return None
            transporte = self._detect_transport(handle)
            path = self.hidraw_path(uniq)
            if path is None:
                return None  # path de libusb: sem nó hidraw para o ioctl
            try:
                data = _read_feature_via_hidraw(
                    path, _CALIBRATION_FEATURE_ID, _CALIBRATION_FEATURE_SIZE
                )
            except OSError as exc:
                logger.info("calibration_read_failed", key=key, err=str(exc))
                return None
        if len(data) != _CALIBRATION_FEATURE_SIZE or data[0] != _CALIBRATION_FEATURE_ID:
            logger.warning(
                "calibration_report_invalido", key=key, tamanho=len(data)
            )
            return None
        if transporte == "bt":
            crc = int.from_bytes(data[-4:], "little")
            if bt_crc32(data[:-4], seed=BT_FEATURE_CRC_SEED) != crc:
                logger.warning("calibration_crc_invalido", key=key)
                return None
        return data

    @property
    def primary_uniq(self) -> str | None:
        """MAC normalizado do controle PRIMÁRIO (None se sem serial/offline).

        FEAT-DSX-CONTROLLER-IDENTITY-01: identidade universal do controle —
        a mesma usada pelo `discover_dualsense_evdevs` (uniq do evdev) e pelo
        `sysfs_leds` (HID_UNIQ). Key de fallback por path retorna None.

        M3 (auditoria): delega a `_key_to_uniq`, que tem a guarda de 12 dígitos
        hex — `norm_mac('/dev/hidraw3')` devolvia um pseudo-MAC ('deda3'), e um
        pseudo-MAC != None furava o guard anti-input-dobrado do co-op
        (coop.py: `primary is None or primary.startswith('path:')`), spawnando um
        jogador secundário NO PRÓPRIO controle do primário. Com None, o guard
        adia o spawn até o MAC real resolver — como a docstring sempre prometeu.
        """
        return self._key_to_uniq(self._primary_key) if self._primary_key else None

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

    # --- estado desejado por controle (PERFIL-01 / 4P-01) ----------------

    @property
    def _desired(self) -> _DesiredOutput:
        """Alias de compatibilidade → `_desired_default` (padrão broadcast).

        O co-op lê `getattr(ctrl, "_desired", None).player_leds` como "o
        padrão do perfil" (coop.py `_profile_player_leds`) — um rename seco
        falharia EM SILÊNCIO (getattr devolvendo None para sempre; o co-op
        desligado pararia de restaurar o player-LED do perfil sem nenhum
        teste quebrando). Leitura apenas; a escrita interna usa
        `_desired_default`/`_desired_by_uniq`.
        """
        return self._desired_default

    def set_auto_output_provider(
        self, fn: Callable[[str], _DesiredOutput | None] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da camada AUTOMÁTICA (COR-03).

        O provider recebe o UNIQ (MAC 12-hex normalizado) de um controle e
        devolve um `_DesiredOutput` com APENAS os campos automáticos
        preenchidos (`led` = cor do slot já escalada pelo brilho, D11;
        `player_leds` = padrão do número do controle, D7) — ou None quando
        não tem opinião (auto desligado, uniq sem slot, vpad). É consultado
        por `_merged_desired_for_key` SOB `_io_lock`: DEVE ser barato e sem
        I/O (nada de disco/HID — só memória). Exceções do provider são
        engolidas com log (a resolução cai no merge histórico) — um provider
        quebrado jamais derruba um reassert de LED.
        """
        with self._io_lock:
            self._auto_output_provider = fn

    def set_game_authority_provider(
        self, fn: Callable[[], str] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da autoridade de exibição.

        NUMA-02 — espelho exato de `set_auto_output_provider`: o daemon
        (GameSignal do lifecycle, tick lento ~2s) injeta uma função que
        devolve a autoridade corrente ('game'|'daemon'|'unknown'). É
        consultada por `_game_wins()` SOB `_io_lock`: DEVE ser leitura de
        estado cacheado, sem I/O. Sem provider o backend é HEAD
        byte-idêntico — remover esta fiação desliga a Onda N inteira
        (rollback de 1 linha, decisão da síntese).
        """
        with self._io_lock:
            self._game_authority_provider = fn

    def _game_wins(self) -> bool:
        """True quando a camada GAME participa do merge (autoridade ≠ 'daemon').

        NUMA-02 — fail-safe assimétrico da síntese: sem provider injetado OU
        exceção no provider ⇒ True (jogo vence = comportamento atual;
        bloquear réplica exige evidência POSITIVA de não-jogo). Só a
        autoridade 'daemon' explícita fecha o gate; 'game', 'unknown' e
        qualquer lixo devolvido mantêm o caminho de hoje.
        """
        provider = self._game_authority_provider
        if provider is None:
            return True
        try:
            return provider() != "daemon"
        except Exception as exc:
            logger.debug("game_authority_provider_falhou", err=str(exc))
            return True

    def _merged_desired_for_key(self, key: str) -> _DesiredOutput:
        """Desired efetivo do controle `key`: MERGE POR CAMPO em 4 camadas.

        Precedência (D5, POR CAMPO): camada GAME (REPLICA-03 — o que o jogo
        escreveu no vpad, viva só durante a sessão uhid) > override explícito
        por-uniq > camada AUTOMÁTICA do provider (COR-03) > default global do
        perfil. Chamar sob `_io_lock` (lê o mapa por-uniq; o provider é
        chamado aqui dentro — barato e sem I/O por contrato de
        `set_auto_output_provider`).

        Key sem MAC (fallback por path) não tem override NEM camada
        automática possível — devolve o default puro (o controle segue só o
        global, comportamento documentado do sprint; a cor automática exige
        identidade estável, D9/D10).

        Nota honesta (D4): com o auto LIGADO, um "Todos" da GUI grava só o
        default — e a automática continuaria vencendo (está acima no merge).
        É exatamente por isso que a semântica D4 manda a GUI DESLIGAR o
        toggle ao aplicar "Todos"; o merge daqui fica honesto e não resolve
        isso por conta própria.
        """
        uniq = self._key_to_uniq(key)
        override = self._desired_by_uniq.get(uniq) if uniq is not None else None
        base = self._desired_default
        provider = self._auto_output_provider
        if provider is not None and uniq is not None:
            try:
                auto = provider(uniq)
            except Exception as exc:
                logger.debug(
                    "auto_output_provider_falhou", uniq=uniq, err=str(exc)
                )
                auto = None
            if auto is not None:
                base = _merge_desired(base, auto)
        resolved = _merge_desired(base, override)
        game = self._game_output_by_uniq.get(uniq) if uniq is not None else None
        # NUMA-02 (gate de exibição em ponto ÚNICO): sob autoridade 'daemon' a
        # camada GAME não entra no merge — este if governa de uma vez o
        # priming, o reassert de hotplug, `reassert_resolved_outputs` e o
        # unmute. Consequência provada nos replays: camada STALE (cliente
        # Steam segurando a sessão uhid sem UHID_CLOSE) é neutralizada no
        # resolve, não defendida — fechar o jogo devolve a paleta em ≤ ~32s.
        if game is not None and self._game_wins():
            resolved = _merge_desired(resolved, game)
        return resolved

    def _record_desired_locked(self, target_key: str | None, fields: dict[str, Any]) -> None:
        """Grava campos do estado desejado no escopo CERTO. Chamar sob `_io_lock`.

        `target_key=None` (broadcast — sem alvo, ou alvo que desconectou, o
        mesmo fallback do `_for_each`): grava no default E LIMPA o campo
        escrito de todos os overrides por-uniq — um "Todos" ao vivo da GUI
        vale para todo mundo; sem a limpeza, "mudei todos para azul,
        repluguei e um voltou verde". Alvo presente: grava SÓ no override do
        MAC do alvo (era o bug provado do 4P-01 — o setter gravava no global
        incondicionalmente e o replug de OUTRO controle herdava o ajuste).
        Alvo sem MAC (key por path): a escrita de hardware acontece, mas não
        há identidade estável para lembrar — log em vez de silêncio.
        """
        if target_key is not None:
            uniq = self._key_to_uniq(target_key)
            if uniq is None:
                logger.debug(
                    "desired_por_controle_sem_mac",
                    key=target_key,
                    campos=sorted(fields),
                )
                return
            override = self._desired_by_uniq.setdefault(uniq, _DesiredOutput())
            for name, value in fields.items():
                setattr(override, name, value)
            return
        for name, value in fields.items():
            setattr(self._desired_default, name, value)
            for override in self._desired_by_uniq.values():
                setattr(override, name, None)
        # Poda overrides que ficaram sem nenhum campo (mapa limpo p/ debug).
        self._desired_by_uniq = {
            uniq: override
            for uniq, override in self._desired_by_uniq.items()
            if any(getattr(override, name) is not None for name in _OUTPUT_FIELDS)
        }

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
            if _is_virtual_hidraw(info.path):
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
        new_handles: list[tuple[str, pydualsense]] = []
        for key, path, is_edge in want:
            if key in existing:
                continue
            # L2: pula se já há handle OU se outro probe concorrente já está
            # abrindo esta key (guard sob `_io_lock`). Marca a key como "em
            # abertura" antes do `_open_one` (caro) e a libera no `finally`.
            with self._io_lock:
                if key in self._handles or key in self._opening:
                    continue
                self._opening.add(key)
            try:
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
                new_handles.append((key, handle))
            except Exception as exc:
                # LIGHTBAR-BT-ADOPT-01 (complemento): falha de UM device não pode
                # abortar o connect() — sem isto, uma exceção do `_open_one` (ex.:
                # permissão hidraw de um 2º controle) pulava `_refresh_sysfs_leds`
                # em TODO tick e, com `_suppress_leds` nascendo True, deixava os
                # handles JÁ abertos suprimidos para sempre (lightbar/player
                # inaplicáveis). Loga e segue para o próximo device.
                logger.debug("backend_open_one_failed", key=key, err=str(exc))
                continue
            finally:
                with self._io_lock:
                    self._opening.discard(key)

        with self._io_lock:
            self._recompute_primary()
            self._offline = not self._handles
            # PERF-MULTI-CONTROLLER-01: throttle do report_thread escala com o
            # nº de controles (base x N, capado) — divide a pressão de USB e de
            # CPU/GIL por controle. Output (LED/trigger/rumble) tolera bem.
            n = max(1, len(self._handles))
            throttle = min(
                REPORT_THREAD_THROTTLE_SEC * n, REPORT_THREAD_THROTTLE_MAX_SEC
            )
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._throttle_sec = throttle
                    # FEAT-NATIVE-OUTPUT-MUTE-01: handle novo aberto durante o
                    # Modo Nativo herda o mute (hotplug com jogo em foco).
                    handle._output_muted = self._output_mute
        # LIGHTBAR-BT-RESET-01: a adoção (feature reads do init da pydualsense)
        # derruba o claim da lightbar no FIRMWARE do DualSense por BT — a
        # lightbar apaga e passa a ignorar as escritas de cor do kernel até um
        # power-off (provado ao vivo 2026-07-17/18). A cura é o report "Reset
        # LED state" (flag1=0x08) que o SDL envia em toda conexão BT e o kernel
        # nunca envia. Enviado AQUI, logo após abrir o handle (pós feature
        # reads) e ANTES do reassert de cor — a próxima escrita sysfs volta a
        # colar. Só BT (USB não tem o claim) e best-effort (falha = sintoma
        # antigo, sem regressão).
        for _key, handle in new_handles:
            with contextlib.suppress(Exception):
                if self._detect_transport(handle) == "bt":
                    from hefesto_dualsense4unix.core.lightbar_reset import (
                        send_release_leds,
                    )

                    if send_release_leds(handle.device):
                        logger.info("lightbar_reset_enviado", key=_key)

        # LIGHTBAR-BT-RESET-02 (Onda L): o 0x08 acima só cobre handles NOVOS. Um
        # wake/resume BT que NÃO reabre o handle também derruba o claim do
        # firmware (o kernel reseta a classe LED para KERNEL_DEFAULT_BLUE, mesmo
        # indicator_dir, logo NÃO é new_key — caso medido 2026-07-20 17:28).
        # Reenvia o 0x08 SÓ na assinatura do wake (nó sysfs voltou ao default do
        # kernel com o desired resolvido diferente); o reassert logo abaixo
        # re-cola cor E player LEDs. Nunca por timer — evita flicker de quem tem
        # o claim intacto. Snapshot sob lock, I/O de nó/handle fora dele (padrão
        # do reassert). Best-effort: falha = sintoma antigo, sem regressão.
        new_keys = {k for k, _ in new_handles}
        with self._io_lock:
            reclaim_candidates = [
                (
                    key,
                    handle,
                    self._sysfs.get(key),
                    self._merged_desired_for_key(key),
                    self._detect_transport(handle),
                )
                for key, handle in self._handles.items()
                if key not in new_keys
            ]
        for key, handle, node, desired, transport in reclaim_candidates:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.core.lightbar_reset import (
                    send_release_leds,
                    should_reclaim_on_wake,
                )

                current = node.get_rgb() if node is not None else None
                if should_reclaim_on_wake(
                    transport, desired.led, current, KERNEL_DEFAULT_BLUE
                ) and send_release_leds(handle.device):
                    logger.info("lightbar_reset_reenviado_wake", key=key)

        # FEAT-DSX-LIGHTBAR-SYSFS-01: (re)mapeia os nós LED do kernel a cada tick
        # de hotplug — cobre controle novo E o nó LED que o kernel às vezes
        # registra com atraso após o hidraw; re-afirma a cor/player ativos nos
        # nós que acabaram de surgir.
        self._refresh_sysfs_leds()
        # re-aplica o perfil ativo nos controles recém-chegados.
        for key, handle in new_handles:
            self._reapply_desired(key, handle)
        # COR-WAKE-01 (fix ao vivo 2026-07-17): re-resolve a cor/LED por-controle
        # em TODA reconciliação de hotplug/wake — não só nos handles/nós que
        # acabaram de surgir. Sintoma provado ao vivo: boot com os DualSense
        # dormindo em BT (ou um resume que faz o kernel resetar a classe LED sem
        # recriar o `inputN` — mesmo `indicator_dir`, logo NÃO é `new_key`)
        # deixava os dois controles na cor default do kernel
        # (`KERNEL_DEFAULT_BLUE` = 0,0,128) até uma ativação MANUAL de perfil.
        # `connect()` roda a cada `backend_hotplug_reconcile`, então este
        # reassert converge o físico ao resolvido (explícita > automática >
        # global) sozinho. É idempotente (reescreve a MESMA cor), pega o
        # `_io_lock` por conta própria e já é no-op em Modo Nativo (output
        # mutado — o jogo é dono do LED).
        self.reassert_resolved_outputs()

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
        # FEAT-DSX-CONTROLLER-IDENTITY-01: o reader passa a mirar o MAC do
        # primário (uniq do evdev == serial hidapi). Antes o finder pegava o
        # MENOR node — com 2+ controles, "menor node" e "primário do backend"
        # divergiam após re-enumeração e o P1 passava a ler OUTRO controle
        # (raiz da duplicação de input no co-op). `retarget` força reabrir no
        # node certo quando necessário.
        self._evdev.retarget(self.primary_uniq)
        # BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01: o EvdevReader cacheia o path no
        # __init__. Se o daemon bootou offline (sem controle), o path ficava
        # None e o hotplug nunca o reavaliava — input caía no HID-raw cru
        # (sticks ~253 em repouso). Re-procura aqui, a cada troca de primário.
        self._evdev.refresh_device()
        # GYRO-01: o espelho de motion do P1 também segue o primário — larga o
        # hidraw antigo; o `path_provider` do reader re-resolve o novo sozinho.
        # Best-effort e não-bloqueante (só fecha um fd), seguro sob o _io_lock.
        if self._motion_reader is not None:
            with contextlib.suppress(Exception):
                self._motion_reader.request_reopen("primary_changed")
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
            self._sysfs = {}

    def _refresh_sysfs_leds(self) -> None:
        """(Re)mapeia cada handle ao seu nó LED do kernel (FEAT-DSX-LIGHTBAR-SYSFS-01).

        Casa a `key` estável do handle (serial/MAC) com o MAC (`uniq`) do nó
        sysfs. Só usa um nó quando ele é GRAVÁVEL pelo usuário do daemon (regra
        udev aplicada) — gate anti-regressão: sem permissão, o controle fica fora
        do mapa e segue pelo caminho pydualsense histórico.

        Marca `_suppress_leds` nos handles cobertos (para o report_thread não
        disputar a lightbar com o kernel) e re-afirma a cor/player ativos nos nós
        que acabaram de surgir (cobre o nó LED que o kernel registra com atraso).

        STATUS-01 (priming + rastreio "escrito por nós"):
          - "nó novo" inclui o nó RECRIADO do mesmo controle (reconnect BT gera
            outro ``inputN`` — o ``indicator_dir`` muda): a classe LED renasce
            ZERADA no probe do kernel e precisa convergir de novo;
          - nó novo cuja cor resolvida é None recebe o azul-default do kernel
            (``KERNEL_DEFAULT_BLUE``) — escrita idempotente com o hardware, só
            para a classe LED espelhar a lightbar que o probe já acendeu;
          - toda escrita de COR bem-sucedida daqui é registrada em
            ``_sysfs_written`` (prova de posse do nó — é o que autoriza o
            handler IPC a ler ``multi_intensity`` como verdade e o único estado
            em que ``0 0 0`` significa "apagada");
          - exceção documentada: em Modo Nativo (muted) NADA disso roda — o
            jogo é dono do LED (o gate histórico cobre reassert E priming); o
            nó novo fica SEM rastreio e o estado por controle sai como
            "desired"/"desconhecida" até o unmute re-afirmar.
        """
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            by_mac = sysfs_leds.discover()
        except Exception as exc:  # ambiente sem /sys, etc. — degrada p/ pydualsense
            logger.debug("sysfs_leds_discover_falhou", err=str(exc))
            by_mac = {}

        with self._io_lock:
            keys = list(self._handles)
            handles = dict(self._handles)
            prev = self._sysfs

        mapping: dict[str, Any] = {}
        for key in keys:
            nk = sysfs_leds.norm_mac(key)
            node = by_mac.get(nk) if nk else None
            if node is not None and node.writable():
                mapping[key] = node
        # Sem fallback single-controle: o casamento é SÓ por MAC. Controle real
        # sempre expõe o MAC (serial == HID_UNIQ) em USB e BT, então o match é
        # confiável; um handle sem MAC (ou um nó de outra máquina) NUNCA é casado
        # por coincidência — evita acoplar a um nó errado e mantém os testes
        # herméticos. Quem não casa segue pelo caminho pydualsense (USB funciona).

        # LIGHTBAR-BT-ADOPT-01 (telemetria): a cobertura sysfs muda raramente
        # (adoção, replug, regra udev) — logar em INFO torna DATÁVEL uma futura
        # regressão de lightbar (a de 2026-07-17 não tinha registro; o logging
        # de LED era debug-only e a janela da quebra ficou sem timestamp).
        # Dispara também quando o conjunto DESCOBERTO muda (handle presente sem
        # nó sysfs): foi exatamente o ponto cego que escondeu a reconexão
        # envenenada de 2026-07-18 00:53 (o 14:3a entrou em `keys` sem nó e o
        # log de cobertura não disparou).
        uncovered = sorted(k for k in keys if k not in mapping)
        if set(mapping) != set(prev) or uncovered != getattr(
            self, "_led_uncovered_prev", None
        ):
            logger.info(
                "sysfs_led_cobertura",
                cobertos=sorted(mapping),
                sem_no_sysfs=uncovered,
            )
        self._led_uncovered_prev = uncovered

        # Marca supressão de LED no report_thread. Coberto pelo sysfs => o
        # kernel é o dono (design original).
        # LIGHTBAR-BT-NEVER-01 (política, estudo 2026-07-18): por BLUETOOTH a
        # pydualsense fica SEMPRE suprimida, coberta ou não — o report BT dela
        # (0.7.5) é MALFORMADO (layout off-by-one, sem o tag 0x10 obrigatório)
        # e um write com flags de LED dentro da janela da máquina de estados da
        # lightbar LATCHEIA a lightbar apagada até o power-off do controle
        # (provado ao vivo: nó de LED atrasado na reconexão BT rebaixava a
        # supressão por 1 tick e re-envenenava). Não há regressão: a cor via
        # pydualsense NUNCA funcionou por BT ("não obedecia por BT" — o motivo
        # de a rota sysfs existir, a36a2e5). Em USB o fallback histórico segue.
        for key, handle in handles.items():
            with contextlib.suppress(Exception):
                # `_suppress_leds` existe no _PinnedPyDualSense (handles de teste
                # podem não ter — daí o suppress(Exception)).
                handle._suppress_leds = (
                    key in mapping or self._detect_transport(handle) == "bt"
                )

        # Re-afirma o perfil de LED ativo nos nós que SURGIRAM agora (cor que o
        # kernel ainda não tinha ou perdeu no connect/resume).
        # FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) NÃO re-afirma — o jogo é
        # dono do LED; o desejado segue guardado e o unmute o re-aplica.
        # PERFIL-01: o valor re-afirmado é o MERGE por controle (default +
        # override do uniq DESTE nó) — nunca o desejado de outro controle.
        # STATUS-01: nó RECRIADO (mesmo MAC, `indicator_dir` diferente) também é
        # "novo" — a classe LED dele renasceu zerada. `getattr` defensivo: nós
        # dublados em teste podem não ter `indicator_dir` (aí compara None==None
        # e nada re-prima à toa).
        def _node_dir(node: Any) -> Any:
            return getattr(node, "indicator_dir", None)

        new_keys = [
            k
            for k in mapping
            if k not in prev or _node_dir(prev[k]) != _node_dir(mapping[k])
        ]
        if not self._output_mute and new_keys:
            with self._io_lock:
                reasserts = [
                    (key, mapping[key], self._merged_desired_for_key(key))
                    for key in new_keys
                ]
            for key, node, desired in reasserts:
                with contextlib.suppress(Exception):
                    # Priming (STATUS-01, refutação 1): sem cor resolvida, a
                    # classe zerada do probe converge para o azul que o kernel
                    # de fato acendeu — e a escrita entra no rastreio (só assim
                    # o handler pode confiar na leitura do nó).
                    cor = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
                    if node.set_rgb(*cor):
                        self.record_sysfs_write(key, cor)
                    if desired.player_leds is not None:
                        node.set_players(desired.player_leds)

        with self._io_lock:
            self._sysfs = mapping
            # Poda do rastreio: nó que saiu do mapa (controle desconectou /
            # perdeu gravabilidade) não tem mais escrita nossa válida — quando
            # voltar, entra como new_key e o priming/reassert re-registra.
            self._sysfs_written = {
                key: rgb for key, rgb in self._sysfs_written.items() if key in mapping
            }

    def record_sysfs_write(self, key: str, rgb: tuple[int, int, int]) -> None:
        """Registra que NÓS escrevemos `rgb` na classe LED do controle `key`.

        STATUS-01 — metade pública do rastreio "escrito por nós": os caminhos
        de escrita sysfs de cor fora desta função (`_for_each_led` do
        `set_led`, `_write_partial_output` do hotplug/`apply_output_for`, o
        reassert do unmute em `set_output_mute`) podem chamá-lo na borda da
        escrita bem-sucedida. Janela ACEITA e documentada (decisão do sprint):
        enquanto esses call sites não chamam (estão fora da fronteira desta
        entrega), o rastreio guarda a cor da última passada de
        priming/reassert — o que ainda basta para o handler IPC, porque o
        rastreio é prova de POSSE do nó (todas as escritas subsequentes do
        backend nesse nó também vão via sysfs) e a COR exibida vem da leitura
        viva (`SysfsLedNode.get_rgb`), não daqui. Em particular, o unmute do
        Modo Nativo re-escreve a MESMA cor resolvida que a última passada já
        registrou.
        """
        with self._io_lock:
            self._sysfs_written[key] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

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
        # FEAT-MOUSE-CURSOR-FEEL-01 (A6): sticks da pydualsense são centrados
        # em 0 — reconverter para cru 0-255. L2/R2 NÃO passam por aqui: já são
        # crus 0-255 na lib (não somar 128 neles).
        return ControllerState(
            battery_pct=battery,
            l2_raw=l2_raw,
            r2_raw=r2_raw,
            connected=self.is_connected(),
            transport=self._transport,
            raw_lx=_centered_stick_to_raw(state.LX),
            raw_ly=_centered_stick_to_raw(state.LY),
            raw_rx=_centered_stick_to_raw(state.RX),
            raw_ry=_centered_stick_to_raw(state.RY),
            buttons_pressed=buttons_fallback,
        )

    # --- output (fan-out p/ TODOS os controles) -------------------------

    def _for_each(
        self,
        op: Callable[[pydualsense], None],
        *,
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
    ) -> None:
        """Aplica `op` ao ALVO de output (ou a cada handle aberto, em broadcast).

        FEAT-DSX-CONTROLLER-SELECTOR-01: se `_output_target_key` está setada E o
        controle ainda está presente em `_handles`, aplica SÓ a esse handle;
        senão (sem alvo, ou alvo desconectou), volta ao broadcast histórico —
        TODOS os controles. 1 handle morto não derruba os outros.

        PERFIL-01: `broadcast=True` IGNORA o seletor (broadcast real — o
        caminho do perfil, que não pode ser sequestrado pelo alvo da GUI);
        `record` grava os campos no estado desejado do MESMO escopo resolvido
        aqui, sob o MESMO lock — alvo e registro nunca divergem (a corrida do
        seletor global mutável que a revisão apontou). O registro acontece
        mesmo offline (perfil ativado sem controle vale para o hotplug).

        Tira um snapshot da lista sob `_io_lock` e faz o HID I/O fora da seção
        crítica (não segura o lock durante a escrita no device).
        """
        with self._io_lock:
            target = self._output_target_key
            if not broadcast and target is not None and target in self._handles:
                handles = [(target, self._handles[target])]
            else:
                target = None
                handles = list(self._handles.items())
            if record:
                self._record_desired_locked(target, record)
        if not handles:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in handles:
            try:
                op(handle)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    def _for_each_led(
        self,
        *,
        sysfs_op: Callable[[Any], bool],
        pydual_op: Callable[[pydualsense], None],
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
    ) -> None:
        """Aplica um output de LED ao ALVO, preferindo a rota sysfs do kernel.

        Mesma resolução de alvo do `_for_each` (seletor de controle ou broadcast),
        mas, por handle: tenta o nó LED do kernel (cor funciona em USB E BT) e, se
        não houver nó coberto ou a escrita falhar, cai no caminho pydualsense
        (hidraw) — garantindo nenhum regresso quando a regra udev não está
        aplicada. FEAT-DSX-LIGHTBAR-SYSFS-01.

        PERFIL-01: `broadcast`/`record` idênticos ao `_for_each` — alvo e
        registro do estado desejado resolvidos juntos, sob o mesmo lock.
        """
        with self._io_lock:
            target = self._output_target_key
            if not broadcast and target is not None and target in self._handles:
                items = [(target, self._handles[target])]
            else:
                target = None
                items = list(self._handles.items())
            if record:
                self._record_desired_locked(target, record)
            sysfs_map = dict(self._sysfs)
            muted = self._output_mute
        if not items:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in items:
            node = sysfs_map.get(key)
            # FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) o JOGO é dono do LED
            # do controle. A rota sysfs escreve DIRETO no /sys (fora do
            # report_thread, que o mute cobre), então sem este gate um perfil/
            # reassert de player-LED/lightbar pisaria no número que o jogo setou.
            # `_desired` já guarda o valor (setado pelo caller) e o unmute o
            # re-aplica ao sysfs — aqui só evitamos tocar o hardware. O pydual_op
            # abaixo apenas atualiza o estado interno (o report_thread mutado não
            # escreve), mantendo o handle coerente para o próximo unmute.
            if node is not None and not muted:
                try:
                    if sysfs_op(node):
                        continue
                except Exception as exc:
                    logger.debug(
                        "sysfs_led_falhou_fallback_pydual", op=what, key=key, err=str(exc)
                    )
            try:
                pydual_op(handle)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    @staticmethod
    def _apply_trigger(handle: pydualsense, side: Side, effect: TriggerEffect) -> None:
        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = PyDualSenseController._coerce_mode(effect.mode)
        for idx, value in enumerate(effect.forces):
            trigger.setForce(idx, value)

    def _reapply_desired(self, key: str, handle: pydualsense) -> None:
        """Re-aplica o estado desejado DESTE controle num handle recém-aberto.

        PERFIL-01 (4P-01): o que se aplica é o MERGE POR CAMPO do default
        broadcast com o override por-uniq do controle `key` — o do controle
        CERTO, nunca o de outro (era o bug provado: mirar o Controle 2 no
        seletor e replugar o Controle 1 o pintava com a cor do 2).

        REPLICA-03: reconexão NO MEIO de uma sessão de jogo (wake BT) — o
        merge já traz a camada game (LED/player) e os blocos crus de trigger
        do jogo são re-pendurados no handle novo, para a posse sobreviver.
        """
        with self._io_lock:
            node = self._sysfs.get(key)
            muted = self._output_mute
            desired = self._merged_desired_for_key(key)
            uniq = self._key_to_uniq(key)
            game_triggers = (
                dict(self._game_triggers_by_uniq.get(uniq, {}))
                if uniq is not None
                else {}
            )
        for side, block in game_triggers.items():
            attr = "_raw_trigger_left" if side == "left" else "_raw_trigger_right"
            with contextlib.suppress(Exception):
                setattr(handle, attr, block)
        self._write_partial_output(
            handle, node, muted, desired, what="reapply_perfil_no_hotplug"
        )

    def _write_partial_output(
        self,
        handle: pydualsense,
        node: Any,
        muted: bool,
        out: _DesiredOutput,
        *,
        what: str,
    ) -> None:
        """Escreve os campos NÃO-None de `out` em UM handle.

        Gatilhos e LED do mic vão sempre por pydualsense (o kernel não os expõe).
        Lightbar e player-LED vão pelo nó sysfs do kernel quando o controle está
        coberto (cor em USB E BT); senão, por pydualsense (fallback histórico).

        FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) a rota sysfs de LED é
        desabilitada (o jogo é dono do LED). `node and not muted` mantém o
        fallback: sem sysfs disponível, o LED cai em handle.light — mas o
        report_thread também está mutado, então nada chega ao hardware; o
        estado interno fica coerente para o unmute re-aplicar.
        """
        from pydualsense.enums import PlayerID

        try:
            if out.trigger_left is not None:
                self._apply_trigger(handle, "left", out.trigger_left)
            if out.trigger_right is not None:
                self._apply_trigger(handle, "right", out.trigger_right)
            if out.led is not None and not (
                node is not None and not muted and node.set_rgb(*out.led)
            ):
                handle.light.setColorI(*out.led)
            if out.player_leds is not None and not (
                node is not None and not muted and node.set_players(out.player_leds)
            ):
                mask = sum(1 << i for i, b in enumerate(out.player_leds) if b)
                handle.light.playerNumber = PlayerID(mask)
            if out.mic_led is not None:
                handle.audio.setMicrophoneLED(out.mic_led)
        except Exception as exc:
            logger.warning("reapply_perfil_no_hotplug_falhou", op=what, err=str(exc))

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        # PERFIL-01: o registro no estado desejado vai para o ESCOPO do alvo
        # (broadcast → default; alvo selecionado → override por-uniq), junto
        # com a resolução do alvo, sob o mesmo lock (`record=`).
        campo = "trigger_left" if side == "left" else "trigger_right"
        self._for_each(
            lambda h: self._apply_trigger(h, side, effect),
            what="set_trigger",
            record={campo: effect},
        )

    def set_led(self, color: tuple[int, int, int]) -> None:
        r, g, b = color
        # Prefere a rota sysfs do kernel (cor funciona em USB E BT); cai no
        # pydualsense (hidraw) quando o controle não está coberto.
        self._for_each_led(
            sysfs_op=lambda node: node.set_rgb(r, g, b),
            pydual_op=lambda h: h.light.setColorI(r, g, b),
            what="set_led",
            record={"led": color},
        )

    def set_rumble(self, weak: int, strong: int) -> None:
        # Rumble é TRANSITÓRIO (efeito de jogo) — NÃO entra em `_desired`, logo
        # não é "ressuscitado" num controle plugado depois.
        def _do(handle: pydualsense) -> None:
            handle.setLeftMotor(strong)
            handle.setRightMotor(weak)

        self._for_each(_do, what="set_rumble")

    def force_rumble_stop(self) -> None:
        """Para os motores de TODOS os controles com um report de stop (HARM-16).

        GUERRA-01 item 2 mudou o keepalive para NEUTRO: `set_rumble(0, 0)` com
        os nossos motores JÁ em 0 (0→0) não emite mais report com flags de
        vibração — de propósito (é o que parava de zerar rumble de terceiros).
        Mas a saída de um modo (Nativo/gamepad) precisa parar um motor que o
        JOGO deixou vibrando por fora (hidraw direto/FF) — aqui forçamos o
        `_rumble_stop_pending` em cada handle: UM report com flags ligados e
        motores 0, e o ciclo seguinte volta ao neutro. Broadcast deliberado
        (ignora o seletor de alvo): sair de modo para TODO mundo.
        """
        with self._io_lock:
            handles = list(self._handles.items())
        for key, handle in handles:
            try:
                handle.setLeftMotor(0)
                handle.setRightMotor(0)
                handle._rumble_stop_pending = True
            except Exception as exc:
                logger.warning(
                    "output_handle_failed", op="force_rumble_stop", key=key,
                    err=str(exc),
                )

    def set_mic_led(self, muted: bool) -> None:
        """Acende/apaga o LED do microfone em TODOS os controles (INFRA-SET-MIC-LED-01).

        Delega para `ds.audio.setMicrophoneLED(bool)`. A pydualsense cuida da
        diferença USB/BT em `prepareReport` (outReport[9] USB / outReport[10] BT).
        """
        flag = bool(muted)
        self._for_each(
            lambda h: h.audio.setMicrophoneLED(flag),
            what="set_mic_led",
            record={"mic_led": flag},
        )

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

        bitmask = sum(1 << i for i, b in enumerate(bits) if b)
        # Prefere a rota sysfs do kernel (player-LED em USB E BT, sem disputa);
        # cai no pydualsense quando o controle não está coberto.
        self._for_each_led(
            sysfs_op=lambda node: node.set_players(bits),
            pydual_op=lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
            what="set_player_leds",
            record={"player_leds": bits},
        )
        logger.debug("player_leds_aplicados bits=%s bitmask=%s", list(bits), bitmask)

    # --- API por-uniq (PERFIL-01 / 4P-01) --------------------------------

    def apply_output_defaults(self, spec: OutputSpec) -> None:
        """Aplica `spec` como PADRÃO do perfil em TODOS os controles.

        Broadcast REAL: IGNORA o seletor de alvo (`_output_target_key`) de
        propósito — os setters clássicos o respeitam, então ativar um perfil
        (manual OU via autoswitch, mesma cadeia) com um alvo selecionado na
        GUI aplicava SÓ no alvo (bug provado do sprint). Grava no
        `_desired_default` SEM limpar os overrides por-uniq: quem substitui o
        mapa na ativação é `reset_output_overrides` (ciclo de vida explícito)
        — um default novo não pode apagar o override que o próprio perfil
        acabou de registrar.
        """
        fields = _spec_fields(spec)
        if not fields:
            return
        with self._io_lock:
            for name, value in fields.items():
                setattr(self._desired_default, name, value)
        if spec.trigger_left is not None:
            efeito_l = spec.trigger_left
            self._for_each(
                lambda h: self._apply_trigger(h, "left", efeito_l),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.trigger_right is not None:
            efeito_r = spec.trigger_right
            self._for_each(
                lambda h: self._apply_trigger(h, "right", efeito_r),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.led is not None:
            r, g, b = spec.led
            self._for_each_led(
                sysfs_op=lambda node: node.set_rgb(r, g, b),
                pydual_op=lambda h: h.light.setColorI(r, g, b),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.player_leds is not None:
            from pydualsense.enums import PlayerID

            bits = spec.player_leds
            bitmask = sum(1 << i for i, b in enumerate(bits) if b)
            self._for_each_led(
                sysfs_op=lambda node: node.set_players(bits),
                pydual_op=lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.mic_led is not None:
            flag = spec.mic_led
            self._for_each(
                lambda h: h.audio.setMicrophoneLED(flag),
                what="apply_output_defaults",
                broadcast=True,
            )

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> None:
        """Aplica `spec` SÓ no controle de MAC `uniq` e registra o override dele.

        PERFIL-01: NÃO passa pelo `_output_target_key` — o alvo é o parâmetro,
        resolvido na borda pelo chamador (por construção imune à corrida do
        seletor global mutável com o executor multi-thread). Controle
        DESCONECTADO: o override fica REGISTRADO no mapa em memória (o hotplug
        lê o mapa, não o JSON do perfil, e aplica quando ele chegar) — só a
        escrita de hardware é pulada.
        """
        fields = _spec_fields(spec)
        if not fields:
            return
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            # Sem MAC 12-hex não há identidade estável (receiver 2.4G, key por
            # path) — fora do mapa, com log em vez de silêncio (regra do sprint).
            logger.warning("apply_output_for_sem_mac_ignorado", uniq=uniq)
            return
        with self._io_lock:
            override = self._desired_by_uniq.setdefault(alvo, _DesiredOutput())
            for name, value in fields.items():
                setattr(override, name, value)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
        if handle is None:
            logger.debug(
                "apply_output_for_desconectado_registrado",
                uniq=alvo,
                campos=sorted(fields),
            )
            return
        self._write_partial_output(
            handle, node, muted, _DesiredOutput(**fields), what="apply_output_for"
        )

    def reset_output_overrides(
        self, overrides: Mapping[str, OutputSpec] | None = None
    ) -> None:
        """SUBSTITUI o mapa de overrides por-uniq inteiro (ativação de perfil).

        Ciclo de vida explícito do PERFIL-01: sem a substituição, o override
        do perfil ANTERIOR ressuscitaria no hotplug sob o perfil novo (e o
        autoswitch troca de perfil o dia inteiro). Overrides de controles
        DESCONECTADOS também entram no mapa (o hotplug lê o mapa em memória).
        Nenhuma escrita de hardware aqui — o chamador aplica na sequência
        (`apply_output_defaults` + `apply_output_for` por controle conectado).
        """
        novo: dict[str, _DesiredOutput] = {}
        for uniq, spec in (overrides or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("override_por_controle_sem_mac_ignorado", uniq=uniq)
                continue
            novo[alvo] = _DesiredOutput(**_spec_fields(spec))
        with self._io_lock:
            self._desired_by_uniq = novo

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        """Rumble mirado no controle de MAC `uniq`, SEM tocar no seletor global.

        PERFIL-01: substitui o flip transitório do `_output_target_key` que o
        `apply_game_rumble` fazia — com o estado desejado keyed pelo alvo lido
        de um global mutável, a corrida com o executor multi-thread
        (max_workers=2) persistiria config no controle errado. O rumble segue
        transitório (nunca entra no desejado). Devolve False quando o MAC não
        casa com nenhum handle (o chamador decide o fallback broadcast).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return False
        try:
            handle.setLeftMotor(strong)
            handle.setRightMotor(weak)
        except Exception as exc:
            logger.warning("output_handle_failed", op="set_rumble_for", key=key, err=str(exc))
        return True

    # --- REPLICA-03: posse do output pelo JOGO (sessão uhid) --------------

    def set_game_trigger_for(self, uniq: str, side: Side, block: bytes) -> bool:
        """Aplica no físico `uniq` o trigger effect CRU que o jogo mandou ao vpad.

        REPLICA-03: `block` são os 11 bytes (modo + 10 parâmetros) do report
        0x02 do jogo, embutidos VERBATIM no report do físico pelo
        `_build_common` (a rota DSTrigger só representa 7 forças e mutilaria
        o efeito). A posse fica registrada em `_game_triggers_by_uniq` — o
        hotplug re-pendura no handle novo e `end_game_session_for` devolve o
        perfil. False = sem identidade estável (MAC) ou bloco inválido.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        block_b = bytes(block)
        if len(block_b) != GAME_TRIGGER_BLOCK_LEN:
            logger.warning(
                "game_trigger_bloco_invalido", uniq=alvo, tamanho=len(block_b)
            )
            return False
        lado = "left" if side == "left" else "right"
        with self._io_lock:
            self._game_triggers_by_uniq.setdefault(alvo, {})[lado] = block_b
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return True  # registrado; o hotplug aplica quando o controle voltar
        attr = "_raw_trigger_left" if lado == "left" else "_raw_trigger_right"
        try:
            # O report_thread detecta a mudança no próximo prepareReport
            # (o dedup `_last_out_report` compara o buffer montado).
            setattr(handle, attr, block_b)
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_game_trigger_for", key=key,
                err=str(exc),
            )
        return True

    def set_game_output_for(
        self,
        uniq: str,
        *,
        led: tuple[int, int, int] | None = None,
        player_leds: tuple[bool, bool, bool, bool, bool] | None = None,
    ) -> bool:
        """Aplica no físico `uniq` a lightbar/player-LED que o jogo pintou no vpad.

        REPLICA-03: grava a camada GAME do desejado (topo do merge — o
        reassert periódico passa a reafirmar a COR DO JOGO, nunca a paleta
        por baixo dela, matando a race verde-limãoazul por construção) e
        escreve no hardware pela rota normal (sysfs preferido, fallback
        pydualsense). Controle desconectado: fica registrado (hotplug aplica).
        False = sem identidade estável (MAC).

        NUMA-02 (retain-latest): sob autoridade 'daemon' (evidência positiva
        de NÃO-jogo — no incidente 14:42, o escritor era o CLIENTE Steam) a
        réplica de exibição é RETIDA: não popula a camada GAME, não escreve
        hardware; `replay_retained_game_outputs()` entrega o valor mais
        recente 1x na abertura do gate. A telemetria `uhid_replica_ativa`
        do vpad segue intacta (é emitida antes de chegar aqui). Réplica
        retida = prova de escritor ativo ⇒ dispara a defesa de exibição,
        rate-limitada (NUMA-03).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        fields: dict[str, Any] = {}
        if led is not None:
            r, g, b = led
            fields["led"] = (int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)
        if player_leds is not None:
            fields["player_leds"] = tuple(bool(x) for x in player_leds)
        if not fields:
            return True
        defender = False
        with self._io_lock:
            # Decisão de gate UMA vez, sob o lock — o sinal pode flipar no
            # tick de outro thread e uma réplica não pode ser retida E
            # aplicada ao mesmo tempo.
            wins = self._game_wins()
            if not wins:
                retido = self._retained_game_outputs.setdefault(alvo, {})
                retido.update(fields)  # retain-latest: 1 valor por categoria
                if self._retained_log_armed:
                    logger.info(
                        "game_output_retido_sem_jogo",
                        uniq=alvo,
                        campos=sorted(fields),
                    )
                    self._retained_log_armed = False
                agora = time.monotonic()
                defender = (
                    self._defend_last_at is None
                    or (agora - self._defend_last_at)
                    >= DEFEND_DISPLAY_MIN_INTERVAL_S
                )
        if not wins:
            if defender:
                self.defend_display()
            return True
        with self._io_lock:
            layer = self._game_output_by_uniq.setdefault(alvo, _DesiredOutput())
            for name, value in fields.items():
                setattr(layer, name, value)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
        if handle is None:
            return True
        self._write_partial_output(
            handle, node, muted, _DesiredOutput(**fields), what="game_output_replica"
        )
        return True

    def replay_retained_game_outputs(self) -> None:
        """Entrega as réplicas RETIDAS na abertura do gate (NUMA-02).

        Chamado pelo lifecycle na transição `daemon→game|unknown`: cada valor
        retido (o MAIS recente por (uniq, categoria)) é entregue exatamente
        1x pelo caminho normal (`set_game_output_for`) — a escrita única de
        player-LED que jogos fazem (FATO 0) atravessa a latência ~2s do
        sinal sem se perder. Risco aceito na síntese: o último valor pode
        ser do CLIENTE Steam, mas cliente e jogo compartilham a numeração do
        Steam Input e o jogo sobrescreve em seguida. Re-arma o log
        `game_output_retido_sem_jogo` (episódio novo). Falha em um controle
        não aborta os demais.
        """
        with self._io_lock:
            retidos = self._retained_game_outputs
            self._retained_game_outputs = {}
            self._retained_log_armed = True
        for alvo, campos in retidos.items():
            with contextlib.suppress(Exception):
                self.set_game_output_for(alvo, **campos)

    def end_game_session_for(self, uniq: str) -> bool:
        """Fim da sessão de jogo do controle `uniq`: devolve perfil/paleta/co-op.

        REPLICA-03 (UHID_CLOSE): a camada GAME e os triggers crus somem; o
        estado físico converge de volta ao desejado resolvido (explícito >
        automático > global). O nó sysfs tem o cache invalidado (GUERRA-01
        item 3): o jogo pode ter escrito a cor por hidraw sem recriar o nó —
        o cache estaria "certo" com o hardware errado. Trigger do jogo sem
        perfil por baixo volta a Off (efeito de jogo não sobrevive à sessão).

        Correção pós-auditoria da Onda N: a réplica RETIDA (NUMA-02,
        `_retained_game_outputs` — escrita sob autoridade 'daemon', ex.: o
        cliente Steam abrindo sessão uhid sem jogo nenhum) também é
        descartada AQUI, no fim da MESMA sessão que a gerou. Sem isso, o
        valor fantasma sobrevive ao UHID_CLOSE (e a qualquer disconnect/
        reconnect físico) e só seria purgado quando a autoridade saísse de
        'daemon' — vazando via `replay_retained_game_outputs()` para a
        PRÓXIMA sessão de jogo real deste controle, totalmente não
        relacionada à que escreveu o valor (o "player 3 verde" acendendo
        antes de o jogo escrever qualquer coisa).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            game = self._game_output_by_uniq.pop(alvo, None)
            triggers = self._game_triggers_by_uniq.pop(alvo, None)
            retido = self._retained_game_outputs.pop(alvo, None)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
            desired = (
                self._merged_desired_for_key(key) if key is not None else None
            )
        if game is None and triggers is None:
            if retido:
                logger.info(
                    "game_output_retido_descartado_no_close",
                    uniq=alvo,
                    campos=sorted(retido),
                )
            return True  # o jogo nunca tocou este controle
        logger.info(
            "game_session_devolvida",
            uniq=alvo,
            lightbar=bool(game is not None and game.led is not None),
            player_leds=bool(game is not None and game.player_leds is not None),
            triggers=sorted(triggers) if triggers else [],
        )
        if handle is None or desired is None:
            return True  # desconectado: o hotplug reaplica o perfil sozinho
        if triggers:
            with contextlib.suppress(Exception):
                handle._raw_trigger_left = None
                handle._raw_trigger_right = None
            lados: tuple[tuple[Side, str], ...] = (
                ("left", "trigger_left"),
                ("right", "trigger_right"),
            )
            for lado, campo in lados:
                if lado not in triggers:
                    continue
                effect = getattr(desired, campo)
                try:
                    if effect is not None:
                        self._apply_trigger(handle, lado, effect)
                    else:
                        self._reset_trigger(handle, lado)
                except Exception as exc:
                    logger.warning(
                        "output_handle_failed", op="end_game_session_trigger",
                        key=key, err=str(exc),
                    )
        restore = _DesiredOutput()
        if game is not None and game.led is not None:
            if node is not None:
                with contextlib.suppress(Exception):
                    node.invalidate_cache()
            restore.led = desired.led  # None = paleta sem opinião: fica como está
        if game is not None and game.player_leds is not None:
            restore.player_leds = desired.player_leds
        self._write_partial_output(
            handle, node, muted, restore, what="game_session_close"
        )
        return True

    @staticmethod
    def _reset_trigger(handle: pydualsense, side: Side) -> None:
        """Volta um gatilho a Off (sem efeito) — o estado de fábrica do firmware."""
        from pydualsense.enums import TriggerModes

        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = TriggerModes.Off
        for idx in range(7):
            trigger.setForce(idx, 0)

    def resolved_player_leds_for(
        self, uniq: str
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """Padrão de player-LED RESOLVIDO do controle `uniq` (leitura pura).

        PERFIL-06: API pública de LEITURA para o revert do co-op — devolve o
        MERGE POR CAMPO (default broadcast + override por-uniq) do campo
        `player_leds`, pelo MESMO resolvedor dos reasserts de hotplug/unmute
        (`_merged_desired_for_key`). `uniq` sem MAC 12-hex (fallback por
        path) não tem override possível → devolve o default puro (o controle
        segue só o global, regra do sprint). None = nenhum perfil/GUI setou
        player-LED ainda — o chamador não escreve nada. Não toca hardware
        nem muta estado.
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq).player_leds

    def resolved_led_for(self, uniq: str) -> tuple[int, int, int] | None:
        """Cor de lightbar RESOLVIDA do controle `uniq` (leitura pura).

        STATUS-01/COR-05: espelho de `resolved_player_leds_for` para o campo
        `led` — o MERGE POR CAMPO (default broadcast + override por-uniq) pelo
        MESMO resolvedor dos reasserts (`_merged_desired_for_key`). É a fonte
        do `lightbar_source == "desired"` do handler IPC: quando o nó sysfs
        não é gravável (escrita foi por hidraw → classe LED stale por
        construção), esta é a última cor que o daemon mandou aplicar.

        Nota (D8 — divergência fundamentada, decidida pelo orquestrador da
        onda): o valor devolvido é PÓS-escala de brilho — `_DesiredOutput.led`
        guarda o RGB como chegou ao `set_led`, e o manager pré-escala
        `lightbar_brightness` na borda (`led_control.py`). O D8 original pedia
        expor também a cor-identidade PRÉ-brilho, mas separá-la exigiria
        refactor do estado desejado (fora do escopo desta frente); o objetivo
        do D8 (traços legíveis com cor escura) foi resolvido por outra via —
        `utils/color_contrast.ensure_min_contrast` clareia preservando o matiz
        na borda da GUI. None = nenhum perfil/GUI setou cor ainda. Não toca
        hardware nem muta estado.
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq).led

    # --- introspecção / leitura do primário -----------------------------

    def describe_controllers(self) -> list[dict[str, object]]:
        """Descreve cada controle conectado (observabilidade — IPC `controller.list`).

        Uma entrada por handle aberto:
        `{index, connected, transport, is_primary, uniq, battery_pct}`.
        O `index` (FEAT-DSX-CONTROLLER-SELECTOR-01) é a POSIÇÃO em
        `list(self._handles)` (0 = primário) — o mesmo número que o seletor de
        controle usa em `set_output_target`.

        FEAT-STATE-PER-CONTROLLER-01: `uniq` é o MAC normalizado do controle
        (mesma normalização do `primary_uniq`; None quando a key é um path sem
        serial) e `battery_pct` é a bateria 0-100 POR CONTROLE lida do handle
        (None quando desconectado ou o firmware ainda não reportou) — a GUI
        identifica cada card e mostra a carga sem chamada IPC extra. Quando
        nenhum controle está conectado, devolve uma única entrada offline
        (preserva o contrato "ao menos um item" do handler legado).
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
                    "uniq": self._key_to_uniq(key),
                    "battery_pct": self._read_battery_opt(handle) if connected else None,
                }
            )
        return out

    @staticmethod
    def _key_to_uniq(key: str) -> str | None:
        """MAC normalizado da key de um handle, ou None quando a key é um path.

        FEAT-STATE-PER-CONTROLLER-01: mesma normalização do `primary_uniq`
        (`norm_mac`), com guarda de comprimento — um MAC real tem exatamente
        12 dígitos hex. A key de fallback por path ("/dev/hidrawN") também
        contém dígitos hex soltos e, sem a guarda, viraria um pseudo-MAC
        ("deda4") — identificador ERRADO no card da GUI.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        normalized = norm_mac(key)
        if normalized is None or len(normalized) != 12:
            return None
        return normalized

    def reassert_resolved_outputs(self, *, verify: bool = False) -> None:
        """Re-aplica o desired RESOLVIDO por-controle (3 camadas) via sysfs.

        COR-03 — fix de integração pego AO VIVO na validação pós-install
        (2026-07-17): a ativação de perfil termina num broadcast do GLOBAL
        (`apply_output_defaults`), que pisa a paleta automática nos controles
        conectados; os reasserts por-key (`_merged_desired_for_key`) só
        rodavam em hotplug/new_keys/unmute — então um boot com os controles
        JÁ conectados ficava com a cor global até o próximo replug. Este
        método é o "unmute sem mute": o manager (ativação de perfil) e o
        ipc_draft_applier ("Aplicar" da GUI) o chamam AO FINAL, para o estado
        físico convergir ao resolvido (explícita > automática > global).

        Escreve pela rota sysfs (os nós do mapa `_sysfs`, com registro no
        rastreio "escrito por nós"). Controle sem nó gravável (sem a regra
        77) segue no caminho pydualsense com o global até o próximo
        `_reapply_desired` — limitação documentada do caminho degradado. Em
        Modo Nativo é no-op (o jogo é dono do LED; o unmute já re-aplica).

        NUMA-03 (``verify=True``): repassa a verificação de escritor
        estrangeiro a `SysfsLedNode.set_rgb`/`set_players_verified` — mas SÓ
        para o nó com autoridade 'daemon' vigente E posse registrada em
        `_sysfs_written` (STATUS-01: leitura de classe sem prova de escrita
        nossa nunca vira verdade — o probe do kernel zera a classe com a
        lightbar acesa). Sem posse ou fora de 'daemon', o nó segue o caminho
        histórico (`verify=False` é byte-idêntico ao HEAD).
        """
        with self._io_lock:
            if self._output_mute:
                return
            # `verify` só vale sob autoridade 'daemon' explícita — em
            # game/unknown/sem-provider a defesa não roda (fail-safe).
            check = verify and not self._game_wins()
            posse = set(self._sysfs_written) if check else set()
            reasserts = [
                (key, node, self._merged_desired_for_key(key))
                for key, node in self._sysfs.items()
            ]
        for key, node, desired in reasserts:
            with contextlib.suppress(Exception):
                verificar = check and key in posse
                if desired.led is not None:
                    ok = (
                        node.set_rgb(*desired.led, verify=True)
                        if verificar
                        else node.set_rgb(*desired.led)
                    )
                    if ok:
                        self.record_sysfs_write(key, desired.led)
                if desired.player_leds is not None:
                    escrever_verificado = (
                        getattr(node, "set_players_verified", None)
                        if verificar
                        else None
                    )
                    if callable(escrever_verificado):
                        escrever_verificado(desired.player_leds)
                    else:
                        node.set_players(desired.player_leds)

    def defend_display(self) -> None:
        """Defesa de exibição: invalida os caches sysfs + reassert verificado.

        NUMA-03 — disparada (a) pelo lifecycle na transição `*→daemon` e
        (b) por réplica de exibição RETIDA (rate-limitada por
        `DEFEND_DISPLAY_MIN_INTERVAL_S` em `set_game_output_for` — réplica
        retida é prova de escritor ativo, e o invalidate alcança até o vetor
        hidraw-direto que a re-leitura de classe não vê; no incidente 14:42,
        repinte ≤2s da escrita estrangeira). NÃO é o reassert incondicional
        do flash azul (GUERRA-01): só em transição ou sob evidência de
        escritor, sempre com teto de frequência. No-op TOTAL sob
        `_output_mute` (Modo Nativo: o jogo é o dono — nada escrito, nem
        repaint). Falha de um nó não aborta os demais (suppress por item do
        reassert).
        """
        with self._io_lock:
            if self._output_mute:
                return
            self._defend_last_at = time.monotonic()
            nodes = list(self._sysfs.values())
        for node in nodes:
            with contextlib.suppress(Exception):
                node.invalidate_cache()
        self.reassert_resolved_outputs(verify=True)

    def set_output_mute(self, muted: bool) -> None:
        """Muta/desmuta TODA escrita de output HID (FEAT-NATIVE-OUTPUT-MUTE-01).

        Modo Nativo = o JOGO é o dono do hidraw: rumble, gatilhos adaptativos e
        LEDs vêm dele. Mutado, o report_thread NÃO escreve nada (nem o
        keepalive — que zerava o rumble do jogo a cada 0.5s, sentido ao vivo no
        Sackboy). Ao desmutar, o dirty-flag é limpo para o estado desejado do
        hefesto ser re-escrito no próximo ciclo (~ms).
        """
        with self._io_lock:
            self._output_mute = bool(muted)
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._output_muted = self._output_mute
                    if not self._output_mute:
                        handle._last_out_report = None
            # FEAT-PARITY-REVIEW-01: snapshot p/ re-aplicar o LED do perfil na
            # rota sysfs ao DESMUTAR (fora do lock). Controles cobertos por sysfs
            # não recebem LED pelo report_thread (_suppress_leds), então só o
            # sysfs restaura a cor/player do perfil ao sair do Modo Nativo.
            # PERFIL-01: valor por controle (merge default + override do uniq).
            reasserts = (
                [
                    (key, node, self._merged_desired_for_key(key))
                    for key, node in self._sysfs.items()
                ]
                if not muted
                else []
            )
        for key, node, desired in reasserts:
            with contextlib.suppress(Exception):
                # STATUS-03: espelha o reassert_resolved_outputs — registrar a
                # POSSE do nó (escrita nossa) mesmo quando o nó surgiu PELA
                # PRIMEIRA VEZ durante o Modo Nativo (reconnect BT no meio do
                # jogo); sem isto, ao desmutar a cor era escrita mas o campo
                # diagnostico da cor ficava como "desconhecida".
                if desired.led is not None and node.set_rgb(*desired.led):
                    self.record_sysfs_write(key, desired.led)
                if desired.player_leds is not None:
                    node.set_players(desired.player_leds)
        logger.info("backend_output_mute", muted=bool(muted))

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
    def _read_battery_opt(ds: pydualsense) -> int | None:
        """Bateria 0-100 de UM handle, ou None quando indisponível.

        FEAT-STATE-PER-CONTROLLER-01: leitura barata — só getattrs no objeto
        `DSBattery` que o report_thread da pydualsense atualiza (sem HID I/O
        extra; seguro fora do `_io_lock`, mesmo cuidado do `read_state`).
        Preserva a distinção "sem dado ainda" (None) de "0%": a GUI não deve
        mostrar 0% falso num controle recém-plugado.
        """
        # HOTFIX-1: battery vive em `ds.battery` (top-level), não em ds.state.
        # DSBattery expõe `Level` (0-100) e `State` (enum BatteryState).
        battery = getattr(ds, "battery", None)
        level = getattr(battery, "Level", None) if battery is not None else None
        if level is None:
            return None
        try:
            value = int(level)
        except (TypeError, ValueError):
            return None
        return max(0, min(100, value))

    @staticmethod
    def _read_battery_raw(ds: pydualsense) -> int:
        # Contrato legado do read_state/get_battery: bateria SEMPRE int
        # (0 quando indisponível). Delega a leitura ao `_read_battery_opt`.
        value = PyDualSenseController._read_battery_opt(ds)
        return 0 if value is None else value

    @staticmethod
    def _coerce_mode(mode: int) -> object:
        from pydualsense.enums import TriggerModes
        try:
            return TriggerModes(mode)
        except ValueError:
            logger.warning("trigger_mode_fora_do_enum_mantendo_raw", mode=mode)
            return mode


__all__ = ["PyDualSenseController"]
