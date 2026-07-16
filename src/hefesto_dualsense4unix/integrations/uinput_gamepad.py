"""Gamepad virtual via python-evdev (W6.3 + FEAT-DSX-GAMEPAD-FLAVOR-01).

Cria `/dev/input/js*` que o kernel registra como um gamepad padrão,
permitindo que jogos recebam o input do DualSense já traduzido/filtrado
pelo daemon (combos sagrados removidos).

Dois **flavors** (a "máscara" que o jogo vê):
  - ``dualsense``: VID Sony + PID do DualSense **Edge** (054c:0df2) → prompts
    PlayStation. O PID é DE PROPÓSITO distinto do físico (0ce6) — invariante
    VPAD-04/VPAD-06: nenhum caminho de criação de vpad pode dividir VID/PID
    com o controle real, senão a launch option persistida na Steam
    (``IGNORE_DEVICES=0x054c/0x0ce6``) esconde físico E vpad juntos e o jogo
    fica com ZERO controles (o bug do estudo de 117 agentes).
  - ``xbox``: VID/PID Xbox 360 (045e:028e) → **prompts Xbox**. Fallback
    para jogos "XInput-only" (Windows-ports via Proton) que ignoram Sony.

Fluxo do daemon:
  - Controle físico lê input via `EvdevReader` (HOTFIX-2).
  - Daemon decide: combo sagrado (HotkeyManager) consome, resto repassa.
  - `UinputGamepad.forward_*()` aplica os eventos no device virtual.
  - Jogo lê o device virtual com a máscara escolhida.

O button mapping (evdev BTN_A/B/X/Y = south/east/north/west) é o mesmo nos
dois flavors — o que muda os prompts é o VID/PID, não os códigos de botão.

FEAT-VPAD-FF-PASSTHROUGH-01 — force-feedback (rumble do JOGO):
  O device virtual anuncia EV_FF (FF_RUMBLE + FF_PERIODIC), então jogos/SDL
  fazem upload de efeitos de vibração NELE. O handshake do kernel
  (UI_FF_UPLOAD/UI_FF_ERASE via EV_UINPUT) e os eventos de play/stop (EV_FF)
  chegam no fd do uinput; `pump_ff()` — chamado a cada tick do poll loop —
  drena tudo isso e entrega o rumble resultante ao `rumble_sink` injetado
  (que escreve nos motores do DualSense físico certo). Por isso o backend
  migrou de python-uinput para python-evdev: o python-uinput não expõe
  `ff_effects_max` nem o handshake de upload — sem eles o kernel recusa
  device com EV_FF, e era exatamente essa a razão de os jogos nunca
  vibrarem o DualSense em "Jogar pelo Hefesto". Ambos os flavors ganham FF
  (o Xbox 360 real também tem rumble; jogos esperam). Ambiente sem suporte
  a FF degrada para o vpad sem EV_FF, sem crash.
"""
from __future__ import annotations

import contextlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Xbox 360 (fallback p/ jogos XInput-only).
XBOX360_VENDOR = 0x045E
XBOX360_PRODUCT = 0x028E
XBOX360_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"

# DualSense (Sony) FÍSICO (054c:0ce6). NÃO entra em máscara de vpad nenhuma:
# é o VID/PID que a launch option IGNORE_DEVICES manda o SDL esconder — um vpad
# com este PID some junto com o físico (VPAD-04). As constantes ficam porque
# identificam o controle REAL em outros módulos (espelham `evdev_reader` e
# `uhid_gamepad.DUALSENSE_PRODUCT`).
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6
DUALSENSE_NAME = "Sony Interactive Entertainment DualSense Wireless Controller"

# DualSense **Edge** — a máscara "dualsense" do vpad (VPAD-04). Espelha o
# `uhid_gamepad.VPAD_PRODUCT`: uhid E uinput apresentam o MESMO Edge 0x0df2,
# então o invariante VPAD-06 (vpad nunca divide VID/PID com o físico) vale em
# TODOS os caminhos de criação, inclusive neste fallback degradado. Ressalva
# honesta (refutação nº 2 do sprint doc): um vpad uinput 0df2 não tem hidraw —
# o SDL não usa o driver HIDAPI PS5 nele e cai no matching evdev com um GUID
# (version 0x3) ausente do gamecontrollerdb; esse mapeamento NUNCA foi validado
# ao vivo, e por isso o `compose_launch` não anuncia IGNORE_DEVICES no ramo
# degradado (ver `daemon_actions.compose_launch`).
DUALSENSE_EDGE_PRODUCT = 0x0DF2
DUALSENSE_EDGE_NAME = (
    "Sony Interactive Entertainment DualSense Edge Wireless Controller"
)

# Bus USB (0x03): apresentar como controle USB real ajuda o match da SDL no
# gamecontrollerdb (o GUID inclui bustype+vendor+product). O default do
# python-evdev é BUS_USB, mas mantemos explícito.
BUS_USB = 0x03

#: Versão do input_id do device virtual. O python-uinput usava 0x3 por default
#: e o GUID SDL inclui a versão — preservamos o valor para o match no
#: gamecontrollerdb não mudar entre releases (validado ao vivo em gameplay).
DEVICE_VERSION = 0x3

#: FEAT-VPAD-FF-PASSTHROUGH-01 — nº máximo de efeitos FF simultâneos que o
#: vpad anuncia ao kernel (`ff_effects_max`). O uinput exige > 0 quando EV_FF
#: está nas capabilities; SDL usa tipicamente 1-2 efeitos por jogo.
MAX_FF_EFFECTS = 16

#: Cap de eventos FF drenados por tick — proteção contra flood no fd (jogo
#: emitindo play/stop em rajada); o excedente fica para o próximo tick.
_FF_MAX_EVENTS_PER_PUMP = 64

# Catálogo de flavors. `name`/`vendor`/`product` definem a máscara.
# VPAD-04: a entrada dualsense usa o Edge (0x0df2) — NUNCA o 0x0ce6 do físico.
FLAVORS: dict[str, dict[str, Any]] = {
    "dualsense": {
        "name": DUALSENSE_EDGE_NAME,
        "vendor": DUALSENSE_VENDOR,
        "product": DUALSENSE_EDGE_PRODUCT,
    },
    "xbox": {
        "name": XBOX360_NAME,
        "vendor": XBOX360_VENDOR,
        "product": XBOX360_PRODUCT,
    },
}
#: SPRINT-GAME-RUMBLE-01: o default é **xbox**, não dualsense. Na época da
#: decisão o vpad dualsense-uinput tinha o MESMO VID/PID do físico (054c:0ce6)
#: e SEM hidraw — o SDL/HIDAPI do jogo adotava o FÍSICO pelo hidraw e IGNORAVA
#: o vpad (rumble in-game MORTO + controle DUPLICADO). Com a máscara Xbox 360
#: (045e:028e) o jogo vê o vpad pelo caminho evdev/FF e a vibração funciona —
#: provado com SDL2 e validado em gameplay. Hoje a máscara DualSense vibra pelo
#: backend uhid (Edge 0x0df2 com hidraw de verdade) e o fallback uinput também
#: é Edge (VPAD-04), mas o default segue xbox: é o piso de compatibilidade que
#: funciona validado em QUALQUER backend. Quem prefere prompts de PlayStation
#: escolhe "dualsense" na GUI/perfil (documentado no README).
DEFAULT_FLAVOR = "xbox"

# Retrocompat: nome histórico apontando para o flavor Xbox.
DEVICE_NAME = XBOX360_NAME


def normalize_flavor(flavor: str | None) -> str:
    """Resolve um flavor válido; cai no default se desconhecido/None."""
    if flavor is None:
        return DEFAULT_FLAVOR
    key = flavor.strip().lower()
    # Sinônimos tolerados na CLI/IPC.
    if key in ("ps", "playstation", "ds", "dualsense"):
        return "dualsense"
    if key in ("xbox", "xbox360", "x360", "xinput"):
        return "xbox"
    return key if key in FLAVORS else DEFAULT_FLAVOR

# Mapeamento canonico Hefesto - Dualsense4Unix (HOTFIX-2) -> evdev constant usado no uinput.
# Layout Xbox: cross=A, circle=B, square=X, triangle=Y.
BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_A",
    "circle": "BTN_B",
    "square": "BTN_X",
    "triangle": "BTN_Y",
    "l1": "BTN_TL",
    "r1": "BTN_TR",
    "create": "BTN_SELECT",
    "options": "BTN_START",
    "ps": "BTN_MODE",
    "l3": "BTN_THUMBL",
    "r3": "BTN_THUMBR",
}


def _build_capabilities(*, with_ff: bool) -> dict[int, Any]:
    """Capabilities do vpad no formato do python-evdev (dict por tipo de evento).

    Eixos 0-255 (igual ao evdev do DualSense) e HAT digital -1..1. Com
    ``with_ff``, anuncia EV_FF com FF_RUMBLE (motores weak/strong 0-65535),
    FF_PERIODIC + formas de onda (o kernel valida a waveform contra os bits do
    device; SDL usa efeito periódico como fallback de rumble em alguns jogos)
    e FF_GAIN (ganho global 0-65535 que a SDL manda por padrão).

    Import local — evita custo no import do módulo e permite ambientes sem a
    lib (o chamador trata ImportError).
    """
    from evdev import AbsInfo, ecodes

    axis = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
    hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
    caps: dict[int, list[Any]] = {
        ecodes.EV_ABS: [
            (ecodes.ABS_X, axis),
            (ecodes.ABS_Y, axis),
            (ecodes.ABS_RX, axis),
            (ecodes.ABS_RY, axis),
            (ecodes.ABS_Z, axis),   # LT
            (ecodes.ABS_RZ, axis),  # RT
            (ecodes.ABS_HAT0X, hat),
            (ecodes.ABS_HAT0Y, hat),
        ],
        ecodes.EV_KEY: [
            ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
            ecodes.BTN_TL, ecodes.BTN_TR,
            ecodes.BTN_SELECT, ecodes.BTN_START, ecodes.BTN_MODE,
            ecodes.BTN_THUMBL, ecodes.BTN_THUMBR,
        ],
    }
    if with_ff:
        caps[ecodes.EV_FF] = [
            ecodes.FF_RUMBLE,
            ecodes.FF_PERIODIC,
            ecodes.FF_SQUARE,
            ecodes.FF_TRIANGLE,
            ecodes.FF_SINE,
            ecodes.FF_GAIN,
        ]
    return caps


@dataclass
class UinputGamepad:
    """Wrapper do device virtual. Lazy-creates no `start()`.

    O default mantém o flavor Xbox para retrocompatibilidade dos call-sites
    antigos; o daemon e a CLA usam `UinputGamepad.for_flavor("dualsense")`.
    """

    name: str = DEVICE_NAME
    vendor: int = XBOX360_VENDOR
    product: int = XBOX360_PRODUCT
    bustype: int = BUS_USB
    flavor: str = "xbox"
    #: FEAT-VPAD-FF-PASSTHROUGH-01: destino do rumble vindo do JOGO via FF.
    #: Recebe (weak, strong) já convertidos para 0-255; injetado por quem cria
    #: o vpad (gamepad.py → controle primário; coop.py → controle do jogador).
    #: None = FF aceito no handshake mas descartado (vpad "mudo").
    rumble_sink: Callable[[int, int], None] | None = None
    #: Relógio monotônico injetável (testes de expiração de duração).
    time_fn: Callable[[], float] = time.monotonic
    #: VPAD-05 — por que o flavor dualsense caiu NESTE backend (uinput), setado
    #: pela factory (`make_virtual_pad`): "uhid_indisponivel",
    #: "uhid_start_falhou", "uhid_bind_falhou" ou "uhid_vetado_pelo_chamador".
    #: None = uinput por design (máscara xbox), não é degradação. Exposto no
    #: `state_full` (`gamepad_emulation.degraded_motivo`) para GUI/doctor.
    fallback_motivo: str | None = None

    _device: Any = None
    #: Módulo `evdev.ecodes` (guardado no start p/ não reimportar por tick).
    _ecodes: Any = None
    _last_buttons: frozenset[str] = field(default_factory=frozenset)
    # PERF-MULTI-CONTROLLER-01: último sexteto analógico emitido — o forward
    # roda a cada tick (60Hz) por vpad; sem delta eram 7 writes/tick/vpad no
    # /dev/uinput mesmo com tudo parado.
    _last_axes: tuple[int, int, int, int, int, int] | None = None
    # -- estado FF (FEAT-VPAD-FF-PASSTHROUGH-01) -------------------------
    #: True quando o device nasceu com EV_FF (ambiente pode degradar sem FF).
    _ff_supported: bool = False
    #: id do efeito → (weak16, strong16, duração_ms) do último upload.
    _ff_effects: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    #: id do efeito em reprodução → deadline monotônico (math.inf = sem fim).
    _ff_playing: dict[int, float] = field(default_factory=dict)
    #: Ganho global (FF_GAIN, 0.0-1.0); SDL manda 0xFFFF (1.0) por padrão.
    _ff_gain: float = 1.0
    #: Último par (weak, strong) 0-255 entregue ao sink — o sink escreve HID,
    #: então só é chamado quando o par MUDOU (throttle por mudança).
    _ff_last_sent: tuple[int, int] = (0, 0)
    #: SPRINT-GAME-RUMBLE-01 — nº de "play" de FF que o JOGO pediu neste vpad
    #: desde a criação (diagnóstico: "o jogo mandou rumble? quantas vezes?").
    #: Incrementa em cada `_start_ff_effect` de efeito válido; exposto no
    #: state_full para a GUI/doctor confirmarem se o jogo enxerga o vpad.
    _ff_play_count: int = 0

    @classmethod
    def for_flavor(
        cls,
        flavor: str | None = DEFAULT_FLAVOR,
        *,
        rumble_sink: Callable[[int, int], None] | None = None,
    ) -> UinputGamepad:
        """Constrói o gamepad com a máscara (VID/PID/nome) do flavor dado.

        `rumble_sink` (FEAT-VPAD-FF-PASSTHROUGH-01) recebe o rumble do jogo
        já em 0-255 (weak, strong); ver docstring do campo.
        """
        key = normalize_flavor(flavor)
        spec = FLAVORS[key]
        return cls(
            name=spec["name"],
            vendor=spec["vendor"],
            product=spec["product"],
            flavor=key,
            rumble_sink=rumble_sink,
        )

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível.

        FEAT-VPAD-FF-PASSTHROUGH-01: tenta criar COM force-feedback (EV_FF);
        em kernel/ambiente sem suporte, degrada para o vpad sem FF (o jogo
        não vibra, input segue funcionando) — nunca crasha.
        """
        if self._device is not None:
            return True
        try:
            from evdev import ecodes
        except ImportError:
            logger.warning("python-evdev não instalado — emulação de gamepad indisponível")
            return False
        device = self._create_device(with_ff=True)
        if device is not None:
            self._ff_supported = True
        else:
            device = self._create_device(with_ff=False)
            if device is None:
                return False
            self._ff_supported = False
            logger.warning("uinput_ff_indisponivel_vpad_sem_rumble", name=self.name)
        self._device = device
        self._ecodes = ecodes
        logger.info("uinput_device_created", name=self.name, flavor=self.flavor,
                    vendor=hex(self.vendor), product=hex(self.product),
                    ff=self._ff_supported)
        return True

    def _create_device(self, *, with_ff: bool) -> Any | None:
        """Cria o UInput do python-evdev; None em falha (o start decide o fallback)."""
        from evdev import UInput

        try:
            return UInput(
                _build_capabilities(with_ff=with_ff),
                name=self.name,
                vendor=self.vendor,
                product=self.product,
                version=DEVICE_VERSION,
                bustype=self.bustype,
                max_effects=MAX_FF_EFFECTS if with_ff else 0,
            )
        except Exception as exc:
            logger.warning("uinput_device_create_failed", err=str(exc), ff=with_ff)
            return None

    def stop(self) -> None:
        if self._device is None:
            return
        # FEAT-VPAD-FF-PASSTHROUGH-01: se o FF do jogo deixou motor ligado,
        # zera o rumble físico antes de fechar (o vpad some; ninguém mais
        # mandaria o stop e o DualSense ficaria vibrando).
        if self._ff_last_sent != (0, 0) and self.rumble_sink is not None:
            with contextlib.suppress(Exception):
                self.rumble_sink(0, 0)
        with contextlib.suppress(Exception):
            self._device.close()
        self._device = None
        self._ecodes = None
        self._last_buttons = frozenset()
        self._last_axes = None
        self._ff_supported = False
        self._ff_effects.clear()
        self._ff_playing.clear()
        self._ff_gain = 1.0
        self._ff_last_sent = (0, 0)
        self._ff_play_count = 0

    def is_active(self) -> bool:
        return self._device is not None

    @property
    def ff_supported(self) -> bool:
        """True se o device virtual nasceu com EV_FF (rumble do jogo roteável)."""
        return self._ff_supported

    @property
    def ff_play_count(self) -> int:
        """Nº de play de FF que o JOGO pediu neste vpad (diagnóstico de rumble)."""
        return self._ff_play_count

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) 0-255 entregue ao sink (rumble do jogo)."""
        return self._ff_last_sent

    @property
    def backend(self) -> str:
        """Sempre "uinput": device de evdev (sem hidraw). É o backend da máscara
        Xbox 360 e o fallback do flavor dualsense quando o uhid não sobe. Mesmo
        degradado o PID é o Edge 0x0df2 (invariante VPAD-06 — nunca o 0ce6 do
        físico), mas sem hidraw o mapeamento SDL desse GUID nunca foi validado:
        o botão de Launch Options usa isto para NÃO anunciar IGNORE_DEVICES no
        ramo degradado (plano B da refutação nº 2 do sprint doc)."""
        return "uinput"

    def forward_analog(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
    ) -> None:
        """Aplica valores analógicos no device virtual (só o que MUDOU).

        PERF-MULTI-CONTROLLER-01: emite apenas os eixos com valor novo e o SYN
        só quando algo foi emitido. Sticks parados = zero writes (o kernel de
        qualquer forma descartaria ABS repetido, mas o write/syscall era pago).
        """
        if self._device is None or self._ecodes is None:
            return
        axes = (lx, ly, rx, ry, l2, r2)
        last = self._last_axes
        if axes == last:
            return
        ec = self._ecodes
        codes = (ec.ABS_X, ec.ABS_Y, ec.ABS_RX, ec.ABS_RY, ec.ABS_Z, ec.ABS_RZ)
        emitted = False
        for idx, code in enumerate(codes):
            if last is None or axes[idx] != last[idx]:
                self._device.write(ec.EV_ABS, code, axes[idx])
                emitted = True
        if emitted:
            self._device.syn()
        self._last_axes = axes

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        """Aplica set de botões pressionados. Diff com último snapshot."""
        if self._device is None or self._ecodes is None:
            return

        newly_pressed = pressed - self._last_buttons
        newly_released = self._last_buttons - pressed

        dpad_x, dpad_y = self._dpad_vector(pressed)
        last_dpad_x, last_dpad_y = self._dpad_vector(self._last_buttons)

        ec = self._ecodes
        for name in newly_pressed:
            code = self._resolve_evdev(name, ec)
            if code is not None:
                self._device.write(ec.EV_KEY, code, 1)
        for name in newly_released:
            code = self._resolve_evdev(name, ec)
            if code is not None:
                self._device.write(ec.EV_KEY, code, 0)

        if dpad_x != last_dpad_x:
            self._device.write(ec.EV_ABS, ec.ABS_HAT0X, dpad_x)
        if dpad_y != last_dpad_y:
            self._device.write(ec.EV_ABS, ec.ABS_HAT0Y, dpad_y)

        self._device.syn()
        self._last_buttons = frozenset(pressed)

    def _resolve_evdev(self, hefesto_name: str, ecodes_mod: Any) -> int | None:
        if hefesto_name in BUTTON_TO_UINPUT:
            key = BUTTON_TO_UINPUT[hefesto_name]
            code = getattr(ecodes_mod, key, None)
            return int(code) if isinstance(code, int) else None
        # l2_btn / r2_btn digital viram triggers ABS (já tratados em analog)
        return None

    # -- force-feedback (FEAT-VPAD-FF-PASSTHROUGH-01) ---------------------

    def pump_ff(self) -> None:
        """Drena o protocolo de FF do vpad e repassa o rumble do jogo ao sink.

        Não-bloqueante; chamado a cada tick do poll loop. Três papéis:
          1. upload/erase (EV_UINPUT): responde o handshake obrigatório do
             kernel (begin/end) e mantém o catálogo local de efeitos
             (id → magnitudes + duração);
          2. play/stop (EV_FF): liga/desliga efeitos (value = nº de
             repetições; 0 = stop) e captura FF_GAIN;
          3. expiração: zera o rumble quando a duração venceu (jogos que dão
             play sem nunca mandar stop).
        Vpad sem FF (degradado) ou parado = no-op.
        """
        device = self._device
        if device is None or not self._ff_supported:
            return
        for _ in range(_FF_MAX_EVENTS_PER_PUMP):
            try:
                event = device.read_one()
            except (BlockingIOError, OSError):
                break  # sem eventos pendentes / fd em estado transitório
            if event is None:
                break
            try:
                self._handle_ff_event(event)
            except Exception as exc:
                logger.warning("vpad_ff_event_failed", err=str(exc))
        self._refresh_ff()

    def _handle_ff_event(self, event: Any) -> None:
        """Trata UM evento vindo do fd do uinput (handshake FF ou play/stop)."""
        ec = self._ecodes
        etype = int(event.type)
        code = int(event.code)
        value = int(event.value)
        if etype == ec.EV_UINPUT and code == ec.UI_FF_UPLOAD:
            upload = self._device.begin_upload(value)
            effect = upload.effect
            # Re-upload do mesmo id ATUALIZA o efeito (jogos "reprogramam" o
            # efeito em vez de criar outro); o deadline de um play em curso
            # não muda, só as magnitudes.
            self._ff_effects[int(effect.id)] = self._parse_ff_effect(effect)
            upload.retval = 0
            self._device.end_upload(upload)
        elif etype == ec.EV_UINPUT and code == ec.UI_FF_ERASE:
            erase = self._device.begin_erase(value)
            effect_id = int(erase.effect_id)
            self._ff_effects.pop(effect_id, None)
            self._ff_playing.pop(effect_id, None)
            erase.retval = 0
            self._device.end_erase(erase)
        elif etype == ec.EV_FF and code == ec.FF_GAIN:
            self._ff_gain = max(0, min(0xFFFF, value)) / 0xFFFF
        elif etype == ec.EV_FF:
            # code = id do efeito (< MAX_FF_EFFECTS, nunca colide com FF_GAIN).
            if value > 0:
                self._start_ff_effect(code, repeats=value)
            else:
                self._ff_playing.pop(code, None)
        # Demais eventos no fd (ex.: eco de EV_SYN) são ignorados.

    def _parse_ff_effect(self, effect: Any) -> tuple[int, int, int]:
        """Extrai (weak16, strong16, duração_ms) de um efeito FF do kernel.

        Conversões (documentadas):
          - FF_RUMBLE: magnitudes 0-65535 dos dois motores, direto do efeito.
          - FF_PERIODIC: UMA magnitude signed (pico da onda, 0-32767) —
            usamos ``|magnitude| * 2`` nos DOIS motores (aproximação padrão de
            quem só tem rumble; é o que a SDL espera).
          - Tipo não suportado: (0, 0) — aceito no handshake (retval 0) mas
            mudo, sem quebrar o jogo.
        A duração vem de `ff_replay.length` (ms; 0 = toca até o stop). O
        `ff_replay.delay` é ignorado (raro; SDL não usa).
        """
        ec = self._ecodes
        duration_ms = int(effect.ff_replay.length)
        etype = int(effect.type)
        if etype == ec.FF_RUMBLE:
            rumble = effect.u.ff_rumble_effect
            weak = int(rumble.weak_magnitude) & 0xFFFF
            strong = int(rumble.strong_magnitude) & 0xFFFF
            return (weak, strong, duration_ms)
        if etype == ec.FF_PERIODIC:
            magnitude = min(0xFFFF, abs(int(effect.u.ff_periodic_effect.magnitude)) * 2)
            return (magnitude, magnitude, duration_ms)
        return (0, 0, duration_ms)

    def _start_ff_effect(self, effect_id: int, *, repeats: int) -> None:
        """Marca o efeito como tocando, com deadline = duração x repetições."""
        params = self._ff_effects.get(effect_id)
        if params is None:
            return  # play de efeito nunca uploadado — ignora
        duration_ms = params[2]
        if duration_ms <= 0:
            deadline = math.inf  # sem duração = toca até stop/erase
        else:
            deadline = self.time_fn() + (duration_ms * max(1, repeats)) / 1000.0
        self._ff_playing[effect_id] = deadline
        # SPRINT-GAME-RUMBLE-01: instrumentação — um play de efeito válido = o
        # jogo pediu rumble neste vpad. Se o contador fica em 0 durante o jogo,
        # o jogo NÃO enxerga o vpad (ex.: máscara DualSense atraindo o hidraw
        # do físico); se sobe mas o controle não vibra, o elo é o sink/hardware.
        self._ff_play_count += 1

    def _refresh_ff(self) -> None:
        """Expira efeitos vencidos e entrega o rumble alvo ao sink (se mudou).

        Efeitos simultâneos SOMAM magnitude (clamp em 0xFFFF) — espelha o
        ff-memless do kernel. Conversão 0-65535 → 0-255 por `>> 8`.
        """
        now = self.time_fn()
        for effect_id in [i for i, deadline in self._ff_playing.items() if now >= deadline]:
            del self._ff_playing[effect_id]
        weak_total = 0
        strong_total = 0
        for effect_id in self._ff_playing:
            params = self._ff_effects.get(effect_id)
            if params is None:
                continue
            weak_total += params[0]
            strong_total += params[1]
        gain = self._ff_gain
        weak = min(0xFFFF, int(weak_total * gain)) >> 8
        strong = min(0xFFFF, int(strong_total * gain)) >> 8
        pair = (weak, strong)
        if pair == self._ff_last_sent:
            return
        self._ff_last_sent = pair
        sink = self.rumble_sink
        if sink is None:
            return
        try:
            sink(weak, strong)
        except Exception as exc:
            logger.warning("vpad_ff_sink_failed", err=str(exc))

    @staticmethod
    def _dpad_vector(pressed: frozenset[str]) -> tuple[int, int]:
        x = 0
        y = 0
        if "dpad_left" in pressed:
            x = -1
        elif "dpad_right" in pressed:
            x = 1
        if "dpad_up" in pressed:
            y = -1
        elif "dpad_down" in pressed:
            y = 1
        return x, y


__all__ = [
    "BUS_USB",
    "BUTTON_TO_UINPUT",
    "DEFAULT_FLAVOR",
    "DEVICE_NAME",
    "DEVICE_VERSION",
    "DUALSENSE_EDGE_NAME",
    "DUALSENSE_EDGE_PRODUCT",
    "DUALSENSE_NAME",
    "DUALSENSE_PRODUCT",
    "DUALSENSE_VENDOR",
    "FLAVORS",
    "MAX_FF_EFFECTS",
    "XBOX360_NAME",
    "XBOX360_PRODUCT",
    "XBOX360_VENDOR",
    "UinputGamepad",
    "normalize_flavor",
]
