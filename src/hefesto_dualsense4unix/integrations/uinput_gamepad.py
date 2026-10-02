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
import functools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from hefesto_dualsense4unix.core.rumble import pedido_mais_forte
from hefesto_dualsense4unix.utils.espera import prontos_para_ler
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Xbox 360 (fallback p/ jogos XInput-only).
XBOX360_VENDOR = 0x045E
XBOX360_PRODUCT = 0x028E
XBOX360_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"

# DualSense (Sony) FÍSICO (054c:0ce6). NÃO entra em máscara de vpad nenhuma:
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6
DUALSENSE_NAME = "Sony Interactive Entertainment DualSense Wireless Controller"

# DualSense **Edge** — a máscara "dualsense" do vpad (VPAD-04). Espelha o
DUALSENSE_EDGE_PRODUCT = 0x0DF2
DUALSENSE_EDGE_NAME = (
    "Sony Interactive Entertainment DualSense Edge Wireless Controller"
)

# É EMULAÇÃO, não suporte a aparelho Nintendo físico: o Hefesto faz o DualSense
# quatro DualSense (decisão dela, 06/09/2026).
NINTENDO_VENDOR = 0x057E
NINTENDO_PROCON_PRODUCT = 0x2009
#: os quatro vpads dela sem abrir nenhum. Os bytes 2-3 do GUID são o **CRC16
#:     DualSense ... (Hefesto P1) .......... 0x8076  7680
#:     DualSense ... (Hefesto P2) .......... 0x7076  7670
#:     DualSense ... (Hefesto P3) .......... 0xe077  77e0
#:     DualSense ... (Hefesto P4) .......... 0xd075  75d0
NINTENDO_PROCON_NAME = (
    "Nintendo Co., Ltd. Pro Controller (Hefesto - Dualsense4Unix virtual)"
)

BUS_USB = 0x03

DEVICE_VERSION = 0x3

MAX_FF_EFFECTS = 16

_FF_MAX_EVENTS_PER_PUMP = 64

_FF_FIO_ACORDA_S = 0.25


@functools.cache
def _uinput_sem_no_proprio(base: type) -> type:
    """A classe do `UInput` que NÃO abre o próprio nó depois de criar."""

    class _UInputSemNoProprio(base):  # type: ignore[misc]
        def _find_device(self, _fd: int) -> None:
            return None

    _UInputSemNoProprio.__name__ = f"{base.__name__}SemNoProprio"
    return _UInputSemNoProprio

FF_TETO_SEM_DURACAO_S = 30.0

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
    "nintendo": {
        "name": NINTENDO_PROCON_NAME,
        "vendor": NINTENDO_VENDOR,
        "product": NINTENDO_PROCON_PRODUCT,
    },
}
#: provado com SDL2 e validado em gameplay. Hoje a máscara DualSense vibra pelo
#:   config vem `None` ou com valor desconhecido. A primeira escolha dela na
#:   nova o jogo recebe a máscara DualSense;
DEFAULT_FLAVOR = "xbox"

DEVICE_NAME = XBOX360_NAME


FLAVOR_SINONIMOS: dict[str, str] = {
    "ps": "dualsense",
    "ps5": "dualsense",
    "playstation": "dualsense",
    "sony": "dualsense",
    "ds": "dualsense",
    "xbox360": "xbox",
    "x360": "xbox",
    "xinput": "xbox",
    "switch": "nintendo",
    "pro": "nintendo",
    "procon": "nintendo",
}


def resolver_flavor(flavor: object) -> str | None:
    """A máscara canônica de `flavor`, ou **None** quando ninguém a reconhece."""
    if not isinstance(flavor, str):
        return None
    key = flavor.strip().lower()
    if key in FLAVORS:
        return key
    return FLAVOR_SINONIMOS.get(key)


def nomes_de_flavor_aceitos() -> tuple[str, ...]:
    """Todo nome que :func:`resolver_flavor` reconhece, ordenado."""
    return tuple(sorted(set(FLAVORS) | set(FLAVOR_SINONIMOS)))


def normalize_flavor(flavor: str | None) -> str:
    """Resolve um flavor válido; cai no default se desconhecido/None."""
    if flavor is None:
        return DEFAULT_FLAVOR
    return resolver_flavor(flavor) or DEFAULT_FLAVOR

# Mapeamento canonico Hefesto - DualSense4Unix (HOTFIX-2) -> evdev constant usado no uinput.
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

#: códigos que o kernel já usa para o DualSense físico
#: DIGITAIS (`BTN_TL2`/`BTN_TR2`, ver :func:`_capacidades_procon`) e quem os
BOTOES_PROCON: dict[str, str] = {
    "cross": "BTN_SOUTH",
    "circle": "BTN_EAST",
    "square": "BTN_WEST",
    "triangle": "BTN_NORTH",
    "l1": "BTN_TL",
    "r1": "BTN_TR",
    "create": "BTN_SELECT",
    "options": "BTN_START",
    "ps": "BTN_MODE",
    "l3": "BTN_THUMBL",
    "r3": "BTN_THUMBR",
}

BOTOES_POR_FLAVOR: dict[str, dict[str, str]] = {
    "dualsense": BUTTON_TO_UINPUT,
    "xbox": BUTTON_TO_UINPUT,
    "nintendo": BOTOES_PROCON,
}

#: Acima deste valor (0-255) o gatilho analógico do DualSense vira o botão
LIMIAR_GATILHO_PRESSIONADO = 32
LIMIAR_GATILHO_SOLTO = 16


def _capacidades_ff(ecodes: Any) -> list[Any]:
    """Os bits de EV_FF, iguais nas três máscaras.

    FF_RUMBLE (motores weak/strong 0-65535), FF_PERIODIC + formas de onda (o
    kernel valida a waveform contra os bits do device; SDL usa efeito periódico
    como fallback de rumble em alguns jogos) e FF_GAIN (ganho global 0-65535
    que a SDL manda por padrão).

    RESSALVA DECLARADA na máscara nintendo: o Pro de verdade anuncia **só**
    `FF_RUMBLE` (`joycon_config_rumble`, `hid-nintendo.c:2321-2322`, um
    `input_ff_create_memless`). O nosso anuncia mais. É superconjunto — nenhum
    jogo perde caminho por isso, e um jogo que só sabe pedir periódico ganha um
    que o Pro real não teria.
    """
    return [
        ecodes.FF_RUMBLE,
        ecodes.FF_PERIODIC,
        ecodes.FF_SQUARE,
        ecodes.FF_TRIANGLE,
        ecodes.FF_SINE,
        ecodes.FF_GAIN,
    ]


def _capacidades_padrao(*, with_ff: bool) -> dict[int, Any]:
    """Capabilities das máscaras `dualsense` e `xbox` (formato python-evdev).

    Eixos 0-255 (igual ao evdev do DualSense) e HAT digital -1..1.

    Este conjunto é uma imitação byte a byte do `xpad`, e é por isso que a
    máscara Xbox funciona: MEDIDO em 07/09/2026, a libSDL2 aplica a este nó o
    mapeamento `a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,rightshoulder:b5,back:b6,
    start:b7,guide:b8,leftstick:b9,rightstick:b10,lefttrigger:a2,leftx:a0,
    lefty:a1,rightx:a3,righty:a4,righttrigger:a5` — os onze botões e os seis
    eixos caem, na ordem de código, exatamente onde a tabela os espera.

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
            (ecodes.ABS_Z, axis),
            (ecodes.ABS_RZ, axis),
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
        caps[ecodes.EV_FF] = _capacidades_ff(ecodes)
    return caps


def _capacidades_procon(*, with_ff: bool) -> dict[int, Any]:
    """Capabilities da máscara `nintendo` — e ela NÃO é a de cima.

    O TERCEIRO SABOR NÃO CABE NO CONJUNTO FIXO, e a prova é uma medição, não
    uma leitura. Com um nó `057e:2009` de pé usando as capabilities do
    `_capacidades_padrao`, a libSDL2 desta máquina aplicou (07/09/2026):

        a:b1,b:b0,back:b9,dpdown:h0.4,...,guide:b11,leftshoulder:b5,
        leftstick:b12,lefttrigger:b7,leftx:a0,lefty:a1,misc1:b4,
        rightshoulder:b6,rightstick:b13,righttrigger:b8,rightx:a2,righty:a3,
        start:b10,x:b2,y:b3

    A SDL casa a tabela dela pelo par VID/PID e **ignora os bytes de versão**
    do GUID — a hipótese de que a versão `0x3` do nosso nó nos deixaria fora do
    catálogo dela é FALSA, e foi medida como falsa. Com onze botões e seis
    eixos, aquela tabela lê o nó errado inteiro: `b11`, `b12` e `b13` não
    existem, `lefttrigger:b7` cai no `BTN_START`, e `rightx:a2` cai no
    **gatilho esquerdo**. O analógico direito ficaria colado no dedo do L2.

    O conjunto abaixo é o do aparelho de verdade, lido no fonte C em
    `assets/dkms/hid-nintendo/hid-nintendo.c` (`joycon_input_create:2432-2436`
    para o ramo `procon`):

    * **14 botões**, `procon_button_mappings:494-509` — e os 14 têm de ser
      DECLARADOS mesmo quando nunca são pressionados, porque `bN` é a POSIÇÃO
      na ordem de código: faltar um empurra todos os seguintes;
    * **`BTN_Z` (b4)** é o botão Capture, o `misc1` da tabela da SDL. Um
      DualSense não tem equivalente; ele nasce declarado e mudo, e é essa
      declaração que mantém `leftshoulder` em b5 e não em b4;
    * **sem `ABS_Z`/`ABS_RZ`** (`joycon_config_left_stick`/`_right_stick`
      registram só X/Y/RX/RY) — no Pro os gatilhos são digitais, e é por isso
      que a tabela da SDL diz `lefttrigger:b7`;
    * **HAT** (`joycon_config_dpad`), igual ao das outras duas máscaras.

    O PREÇO, DECLARADO E NÃO ESCONDIDO: **sob esta máscara o L2/R2 deixa de
    ser analógico.** O aparelho imitado não tem esse eixo; um jogo que leia
    aceleração progressiva do gatilho recebe ligado/desligado. Quem quer o
    gatilho adaptativo e a curva escolhe `dualsense` ou `xbox`.

    A ÚNICA divergência de propósito é o domínio dos eixos: 0-255 aqui, contra
    `-32767..32767` do Pro real (`JC_MAX_STICK_MAG`, `hid-nintendo.c:213`). A
    SDL normaliza pelo min/max que o próprio nó declara — foi assim que a
    máscara Xbox sempre funcionou com 0-255 contra o `xpad`, que usa signed —,
    e manter 0-255 evita mexer no domínio de valor do `forward_analog`, que é
    partilhado pelas três máscaras.
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
            (ecodes.ABS_HAT0X, hat),
            (ecodes.ABS_HAT0Y, hat),
        ],
        ecodes.EV_KEY: [
            ecodes.BTN_SOUTH,
            ecodes.BTN_EAST,
            ecodes.BTN_NORTH,
            ecodes.BTN_WEST,
            ecodes.BTN_Z,
            ecodes.BTN_TL,
            ecodes.BTN_TR,
            ecodes.BTN_TL2,
            ecodes.BTN_TR2,
            ecodes.BTN_SELECT,
            ecodes.BTN_START,
            ecodes.BTN_MODE,
            ecodes.BTN_THUMBL,
            ecodes.BTN_THUMBR,
        ],
    }
    if with_ff:
        caps[ecodes.EV_FF] = _capacidades_ff(ecodes)
    return caps


class _FabricaDeCapacidades(Protocol):
    """A forma dos dois construtores de capabilities — `(*, with_ff)`."""

    def __call__(self, *, with_ff: bool) -> dict[int, Any]: ...


CAPACIDADES_POR_FLAVOR: dict[str, _FabricaDeCapacidades] = {
    "dualsense": _capacidades_padrao,
    "xbox": _capacidades_padrao,
    "nintendo": _capacidades_procon,
}


def _build_capabilities(*, with_ff: bool, flavor: str = DEFAULT_FLAVOR) -> dict[int, Any]:
    """Capabilities da máscara `flavor`. Sabor desconhecido cai no padrão."""
    construtor = CAPACIDADES_POR_FLAVOR.get(flavor, _capacidades_padrao)
    return construtor(with_ff=with_ff)


@dataclass
class UinputGamepad:
    """Wrapper do device virtual. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    vendor: int = XBOX360_VENDOR
    product: int = XBOX360_PRODUCT
    bustype: int = BUS_USB
    flavor: str = "xbox"
    rumble_sink: Callable[[int, int], None] | None = None
    time_fn: Callable[[], float] = time.monotonic
    #: `state_full` (`gamepad_emulation.degraded_motivo`) para GUI/doctor.
    fallback_motivo: str | None = None
    aparelho: str | None = None

    _device: Any = None
    _ecodes: Any = None
    _last_buttons: frozenset[str] = field(default_factory=frozenset)
    _last_axes: tuple[int, int, int, int, int, int] | None = None
    _ff_supported: bool = False
    _ff_effects: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    _ff_playing: dict[int, float] = field(default_factory=dict)
    _ff_gain: float = 1.0
    _ff_last_sent: tuple[int, int] = (0, 0)
    #: state_full para a GUI/doctor confirmarem se o jogo enxerga o vpad.
    _ff_play_count: int = 0
    #: (`app/actions/rumble_actions.texto_dos_pedidos_de_vibracao`) pergunta
    _ff_nao_nulo_count: int = 0
    _ff_maior_pedido: tuple[int, int] = (0, 0)
    _ff_descartado_count: int = 0
    _ff_fio: threading.Thread | None = None
    _ff_trava: threading.Lock = field(default_factory=threading.Lock)
    _ff_pare: threading.Event = field(default_factory=threading.Event)

    @classmethod
    def for_flavor(
        cls,
        flavor: str | None = DEFAULT_FLAVOR,
        *,
        rumble_sink: Callable[[int, int], None] | None = None,
        identity: str | None = None,
    ) -> UinputGamepad:
        """Constrói o gamepad com a máscara (VID/PID/nome) do flavor dado."""
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
        )

        key = mascara_efetiva(identity, flavor)
        spec = FLAVORS[key]
        return cls(
            name=spec["name"],
            vendor=spec["vendor"],
            product=spec["product"],
            flavor=key,
            rumble_sink=rumble_sink,
        )

    @property
    def mascara_no_jogo(self) -> str:
        """O aparelho que o jogo vê: o `aparelho` vestido, ou a própria máscara.

        É por ele, e não pelo `flavor`, que o nó nasce (nome, VID/PID e
        capacidades) e que os botões e gatilhos saem: um Xbox 360 com a tabela
        do Pro trocaria o X e o Y de lugar e mandaria o L2 como botão.
        """
        return self.aparelho or self.flavor

    def vestir(self, aparelho: str) -> None:
        """Veste este pad, ainda não criado, com o aparelho de outra máscara.

        NO-MODO-XBOX-TUDO-FUNCIONA-01. O `flavor` fica: é a escolha do cartão,
        que o daemon compara para decidir se recria. Muda o que o kernel
        registra, e só antes do `start()`: um nó já de pé não troca de VID/PID.
        """
        if self._device is not None:
            raise RuntimeError("o pad já nasceu; vestir é antes do start()")
        spec = FLAVORS[aparelho]
        self.aparelho = aparelho
        self.name = spec["name"]
        self.vendor = spec["vendor"]
        self.product = spec["product"]

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível."""
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
        if self._ff_supported:
            self._iniciar_o_fio_da_vibracao()
        logger.info("uinput_device_created", name=self.name, flavor=self.flavor,
                    no_jogo=self.mascara_no_jogo,
                    vendor=hex(self.vendor), product=hex(self.product),
                    ff=self._ff_supported)
        return True

    def _iniciar_o_fio_da_vibracao(self) -> None:
        """Sobe o fio que responde a vibração na hora (só com fd de verdade)."""
        fd = getattr(self._device, "fd", None)
        if not isinstance(fd, int) or fd < 0:
            return
        self._ff_pare = threading.Event()
        fio = threading.Thread(
            target=self._atender_a_vibracao,
            args=(self._device, fd, self._ff_pare),
            name=f"hefesto-ff-{self.mascara_no_jogo}",
            daemon=True,
        )
        self._ff_fio = fio
        try:
            fio.start()
        except RuntimeError as exc:
            logger.warning("uinput_fio_da_vibracao_nao_nasceu", err=str(exc),
                           name=self.name)
            self._ff_fio = None

    def _atender_a_vibracao(self, device: Any, fd: int, pare: threading.Event) -> None:
        """O laço do fio: acorda quando o fd tem evento e atende na hora."""
        while not pare.is_set():
            try:
                prontos = prontos_para_ler([fd], _FF_FIO_ACORDA_S)
            except (OSError, ValueError):
                return
            if not prontos or pare.is_set():
                continue
            with self._ff_trava:
                for _ in range(_FF_MAX_EVENTS_PER_PUMP):
                    try:
                        event = device.read_one()
                    except (BlockingIOError, OSError):
                        break
                    if event is None:
                        break
                    try:
                        self._handle_ff_event(event)
                    except Exception as exc:
                        logger.warning("vpad_ff_event_failed", err=str(exc))

    def _create_device(self, *, with_ff: bool) -> Any | None:
        """Cria o UInput do python-evdev; None em falha (o start decide o fallback)."""
        from evdev import UInput

        fabrica = _uinput_sem_no_proprio(UInput) if isinstance(UInput, type) else UInput
        try:
            return fabrica(
                _build_capabilities(with_ff=with_ff, flavor=self.mascara_no_jogo),
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
        """Fecha o pad UMA vez, mesmo com dois `stop()` ao mesmo tempo."""
        fio = getattr(self, "_ff_fio", None)
        if self._device is None and fio is None:
            return
        if fio is not None:
            self._ff_pare.set()
            fio.join(timeout=2 * _FF_FIO_ACORDA_S + 0.5)
            if self._ff_fio is fio:
                self._ff_fio = None
        device = self.__dict__.pop("_device", None)
        if device is None:
            return
        # mandaria o stop e o DualSense ficaria vibrando).
        if self._ff_last_sent != (0, 0) and self.rumble_sink is not None:
            with contextlib.suppress(Exception):
                self.rumble_sink(0, 0)
        with contextlib.suppress(Exception):
            device.close()
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
        self._ff_nao_nulo_count = 0
        self._ff_maior_pedido = (0, 0)
        self._ff_descartado_count = 0

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
    def ff_nao_nulo_count(self) -> int:
        """Nº de pedidos com FORÇA — os que fariam o motor mexer."""
        return self._ff_nao_nulo_count

    @property
    def ff_maior_pedido(self) -> tuple[int, int]:
        """Maior par (weak, strong) pedido pelo jogo — "dava para sentir?"."""
        return self._ff_maior_pedido

    @property
    def ff_descartado_count(self) -> int:
        """Nº de play de efeito que NÃO tínhamos no catálogo (perdido por nós)."""
        return self._ff_descartado_count

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) 0-255 entregue ao sink (rumble do jogo)."""
        return self._ff_last_sent

    @property
    def backend(self) -> str:
        """Sempre "uinput": device de evdev (sem hidraw). É o backend da máscara"""
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
        """Aplica valores analógicos no device virtual (só o que MUDOU)."""
        if self._device is None or self._ecodes is None:
            return
        axes = (lx, ly, rx, ry, l2, r2)
        last = self._last_axes
        if axes == last:
            return
        ec = self._ecodes
        if self.mascara_no_jogo == "nintendo":
            self._forward_analog_procon(axes, last, ec)
            return
        codes = (ec.ABS_X, ec.ABS_Y, ec.ABS_RX, ec.ABS_RY, ec.ABS_Z, ec.ABS_RZ)
        emitted = False
        for idx, code in enumerate(codes):
            if last is None or axes[idx] != last[idx]:
                self._device.write(ec.EV_ABS, code, axes[idx])
                emitted = True
        if emitted:
            self._device.syn()
        self._last_axes = axes

    def _forward_analog_procon(
        self,
        axes: tuple[int, int, int, int, int, int],
        last: tuple[int, int, int, int, int, int] | None,
        ec: Any,
    ) -> None:
        """O mesmo trabalho sob a máscara `nintendo`: 4 eixos + 2 botões."""
        emitido = False
        for idx, code in enumerate((ec.ABS_X, ec.ABS_Y, ec.ABS_RX, ec.ABS_RY)):
            if last is None or axes[idx] != last[idx]:
                self._device.write(ec.EV_ABS, code, axes[idx])
                emitido = True
        for idx, code in ((4, ec.BTN_TL2), (5, ec.BTN_TR2)):
            antes = self._gatilho_apertado(last[idx], False) if last else False
            agora = self._gatilho_apertado(axes[idx], antes)
            if agora != antes:
                self._device.write(ec.EV_KEY, code, 1 if agora else 0)
                emitido = True
        if emitido:
            self._device.syn()
        self._last_axes = axes

    @staticmethod
    def _gatilho_apertado(valor: int, antes: bool) -> bool:
        """O gatilho analógico (0-255) como bit, com histerese."""
        if antes:
            return valor > LIMIAR_GATILHO_SOLTO
        return valor >= LIMIAR_GATILHO_PRESSIONADO

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
        tabela = BOTOES_POR_FLAVOR.get(self.mascara_no_jogo, BUTTON_TO_UINPUT)
        if hefesto_name in tabela:
            key = tabela[hefesto_name]
            code = getattr(ecodes_mod, key, None)
            return int(code) if isinstance(code, int) else None
        return None


    def pump_ff(self) -> None:
        """Drena o protocolo de FF do vpad e repassa o rumble do jogo ao sink."""
        device = self._device
        if device is None or not self._ff_supported:
            return
        fio = getattr(self, "_ff_fio", None)
        if fio is not None and fio.is_alive():
            with self._ff_trava:
                self._refresh_ff()
            return
        for _ in range(_FF_MAX_EVENTS_PER_PUMP):
            try:
                event = device.read_one()
            except (BlockingIOError, OSError):
                break
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
            if value > 0:
                self._start_ff_effect(code, repeats=value)
            else:
                self._ff_playing.pop(code, None)

    def _parse_ff_effect(self, effect: Any) -> tuple[int, int, int]:
        """Extrai (weak16, strong16, duração_ms) de um efeito FF do kernel."""
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
            self._ff_descartado_count += 1
            return
        duration_ms = params[2]
        if duration_ms <= 0:
            deadline = self.time_fn() + FF_TETO_SEM_DURACAO_S
        else:
            deadline = self.time_fn() + (duration_ms * max(1, repeats)) / 1000.0
        self._ff_playing[effect_id] = deadline
        # o jogo NÃO enxerga o vpad (ex.: máscara DualSense atraindo o hidraw
        self._ff_play_count += 1

    def _refresh_ff(self) -> None:
        """Expira efeitos vencidos e entrega o rumble alvo ao sink (se mudou)."""
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
        if weak or strong:
            self._ff_nao_nulo_count += 1
            self._ff_maior_pedido = pedido_mais_forte(self._ff_maior_pedido, pair)
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
    "BOTOES_POR_FLAVOR",
    "BOTOES_PROCON",
    "BUS_USB",
    "BUTTON_TO_UINPUT",
    "CAPACIDADES_POR_FLAVOR",
    "DEFAULT_FLAVOR",
    "DEVICE_NAME",
    "DEVICE_VERSION",
    "DUALSENSE_EDGE_NAME",
    "DUALSENSE_EDGE_PRODUCT",
    "DUALSENSE_NAME",
    "DUALSENSE_PRODUCT",
    "DUALSENSE_VENDOR",
    "FLAVORS",
    "FLAVOR_SINONIMOS",
    "LIMIAR_GATILHO_PRESSIONADO",
    "LIMIAR_GATILHO_SOLTO",
    "MAX_FF_EFFECTS",
    "NINTENDO_PROCON_NAME",
    "NINTENDO_PROCON_PRODUCT",
    "NINTENDO_VENDOR",
    "XBOX360_NAME",
    "XBOX360_PRODUCT",
    "XBOX360_VENDOR",
    "UinputGamepad",
    "nomes_de_flavor_aceitos",
    "normalize_flavor",
    "resolver_flavor",
]
