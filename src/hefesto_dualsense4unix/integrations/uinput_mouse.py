"""Emulação de mouse+teclado via python-uinput a partir do DualSense (FEAT-MOUSE-01/02).

Cria um device virtual uinput expondo:
  - BTN_LEFT, BTN_RIGHT, BTN_MIDDLE
  - REL_X, REL_Y (movimento) e REL_WHEEL, REL_HWHEEL (rolagem)
  - KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT (D-pad → setas)
  - KEY_ENTER, KEY_ESC (Circle → Enter, Square → Esc — FEAT-MOUSE-02)

Mapeamento canônico (FEAT-MOUSE-01/02, decidido pelo usuário):

| DualSense                | Saída emulada          | evdev code    |
|--------------------------|------------------------|---------------|
| Cross (X) ou L2          | Botão esquerdo         | BTN_LEFT      |
| Triangle () ou R2       | Botão direito          | BTN_RIGHT     |
| R3                       | Botão do meio          | BTN_MIDDLE    |
| Circle ()               | Enter                  | KEY_ENTER     |
| Square (□)               | Esc                    | KEY_ESC       |
| D-pad up/down/left/right | Setas do teclado       | KEY_*         |
| Analógico esquerdo       | Movimento              | REL_X/REL_Y   |
| Analógico direito        | Rolagem                | REL_WHEEL/REL_HWHEEL |

Política:
  - `dispatch()` é chamado a cada tick do poll loop (default 60 Hz) com o
    snapshot dos sticks + triggers analógicos + conjunto de botões canônicos.
    O período do tick vem de `poll_hz` (passado pelo daemon na criação — não
    é hardcodado aqui).
  - Botões têm edge-trigger (press/release só no delta). Estado anterior
    guardado na instância via `_last_buttons_emulated`.
  - Movimento (FEAT-MOUSE-CURSOR-FEEL-01): pipeline float com normalização
    radial, deadzone radial REESCALADA (dz=20/128, resposta contínua a partir
    de zero na borda), curva expo (`m ** MOUSE_EXPO`) e velocidade-alvo em
    px/s reais (`curved * mouse_speed * MOUSE_PX_PER_SEC_STEP`). O delta por
    tick é acumulado com carry fracionário (`_stick_carry_*`) — sub-pixel
    nunca é truncado fora, então toda velocidade > 0 eventualmente move.

    Tabela nível → px/s máximos (deflexão total):

    | speed |  px/s | speed |  px/s |
    |-------|-------|-------|-------|
    |   1   |   125 |   7   |   875 |
    |   2   |   250 |   8   |  1000 |
    |   3   |   375 |   9   |  1125 |
    |   4   |   500 |  10   |  1250 |
    |   5   |   625 |  11   |  1375 |
    |   6   |   750 |  12   |  1500 |

  - Rolagem usa deadzone maior (40/128) e é rate-limited a 1 evento por 50ms
    (via `time.monotonic`, imune a NTP jumps).
  - Device só é criado via `start()` quando toggle explícito é ligado. Default OFF.
"""
from __future__ import annotations

import contextlib
import math
import time
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Mouse+Keyboard"

STICK_CENTER = 128
MOVE_DEADZONE = 20
SCROLL_DEADZONE = 40
SCROLL_RATE_LIMIT_SEC = 0.050
DEFAULT_MOUSE_SPEED = 6
DEFAULT_SCROLL_SPEED = 1

MOUSE_SPEED_MIN, MOUSE_SPEED_MAX = 1, 12
SCROLL_SPEED_MIN, SCROLL_SPEED_MAX = 1, 5
TRIGGER_PRESS_THRESHOLD = 64

MOUSE_EXPO = 1.6
MOUSE_PX_PER_SEC_STEP = 125.0
# daemon). Os callsites reais passam `config.poll_hz`.
DEFAULT_POLL_HZ = 60

TOUCHPAD_SENSITIVITY = 0.45

BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_LEFT",
    "triangle": "BTN_RIGHT",
    "r3": "BTN_MIDDLE",
}

DPAD_TO_KEY: dict[str, str] = {
    "dpad_up": "KEY_UP",
    "dpad_down": "KEY_DOWN",
    "dpad_left": "KEY_LEFT",
    "dpad_right": "KEY_RIGHT",
}

EDGE_KEY_MAP: dict[str, str] = {
    "circle": "KEY_ENTER",
    "square": "KEY_ESC",
}


def _build_capabilities() -> list[tuple[Any, ...]]:
    """Lista de eventos que o uinput device expõe. Import lazy."""
    import uinput

    rels = [
        uinput.REL_X,
        uinput.REL_Y,
        uinput.REL_WHEEL,
        uinput.REL_HWHEEL,
    ]
    buttons = [
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT,
        uinput.BTN_MIDDLE,
    ]
    keys = [
        uinput.KEY_UP,
        uinput.KEY_DOWN,
        uinput.KEY_LEFT,
        uinput.KEY_RIGHT,
        uinput.KEY_ENTER,
        uinput.KEY_ESC,
    ]
    return [*rels, *buttons, *keys]


def _compute_move_px_per_sec(lx: int, ly: int, speed: int) -> tuple[float, float]:
    """Converte o stick esquerdo (0-255 por eixo) em velocidade-alvo (px/s)."""
    nx = (lx - STICK_CENTER) / STICK_CENTER
    ny = (ly - STICK_CENTER) / STICK_CENTER
    mag = math.hypot(nx, ny)
    dz = MOVE_DEADZONE / STICK_CENTER
    if mag <= dz:
        return 0.0, 0.0
    m = min(1.0, (mag - dz) / (1.0 - dz))
    curved = m ** MOUSE_EXPO
    vel = curved * (speed * MOUSE_PX_PER_SEC_STEP)
    return vel * (nx / mag), vel * (ny / mag)


def _compute_scroll_step(raw: int) -> int:
    """Converte valor 0-255 de stick direito em passo de rolagem discreto."""
    offset = raw - STICK_CENTER
    if abs(offset) < SCROLL_DEADZONE:
        return 0
    return 1 if offset > 0 else -1


@dataclass
class UinputMouseDevice:
    """Wrapper do device virtual de mouse+teclado. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    mouse_speed: int = DEFAULT_MOUSE_SPEED
    scroll_speed: int = DEFAULT_SCROLL_SPEED
    poll_hz: int = DEFAULT_POLL_HZ

    # quando ninguém escolhe nada: `set_button_actions` é quem os troca, e o
    # perfil sem `button_actions` nunca o chama.
    _mapa_botoes: dict[str, str] = field(
        default_factory=lambda: dict(BUTTON_TO_UINPUT))
    _mapa_dpad: dict[str, str] = field(default_factory=lambda: dict(DPAD_TO_KEY))
    _mapa_tap: dict[str, str] = field(default_factory=lambda: dict(EDGE_KEY_MAP))

    _device: Any = None
    _uinput_mod: Any = None
    _last_buttons_emulated: frozenset[str] = field(default_factory=frozenset)
    _last_scroll_at: float = -math.inf
    _prev_edge_keys: frozenset[str] = field(default_factory=frozenset)
    _tp_carry_x: float = 0.0
    _tp_carry_y: float = 0.0
    _giro_carry_x: float = 0.0
    _giro_carry_y: float = 0.0
    _stick_carry_x: float = 0.0
    _stick_carry_y: float = 0.0

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível ou módulo ausente."""
        if self._device is not None:
            return True
        try:
            import uinput
        except ImportError:
            logger.warning("python-uinput não instalado — emulação de mouse indisponível")
            return False
        try:
            caps = _build_capabilities()
            self._device = uinput.Device(caps, name=self.name)
            self._uinput_mod = uinput
            self._stick_carry_x = 0.0
            self._stick_carry_y = 0.0
            logger.info("uinput_mouse_created", name=self.name)
            return True
        except Exception as exc:
            logger.warning("uinput_mouse_create_failed", err=str(exc))
            return False

    def stop(self) -> None:
        if self._device is None:
            return
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._uinput_mod = None
        self._last_buttons_emulated = frozenset()
        self._last_scroll_at = -math.inf
        self._prev_edge_keys = frozenset()
        self._tp_carry_x = 0.0
        self._tp_carry_y = 0.0
        self._giro_carry_x = 0.0
        self._giro_carry_y = 0.0
        self._stick_carry_x = 0.0
        self._stick_carry_y = 0.0

    def is_active(self) -> bool:
        return self._device is not None

    def set_speed(self, mouse_speed: int | None = None,
                  scroll_speed: int | None = None) -> None:
        """Ajusta velocidades em runtime (sem recriar device)."""
        if mouse_speed is not None:
            self.mouse_speed = max(MOUSE_SPEED_MIN, min(MOUSE_SPEED_MAX,
                                                        int(mouse_speed)))
        if scroll_speed is not None:
            self.scroll_speed = max(SCROLL_SPEED_MIN, min(SCROLL_SPEED_MAX,
                                                          int(scroll_speed)))

    def set_button_actions(
        self,
        do_mouse: dict[str, str] | None,
        calados: frozenset[str] | None = None,
    ) -> None:
        """Troca o que os botões fazem NESTE device. `None` volta ao de fábrica.

        FEAT-ACOES-DE-BOTAO-01 (01/09/2026). `do_mouse` é a primeira sacola do
        `core/acoes_de_botao.resolver()` — botão -> `BTN_*` —, e é o perfil que
        a decide. Sem chamada, o device segue com os três mapas de fábrica, que
        é o comportamento de sempre.

        OS TRÊS MAPAS SÃO RECONSTRUÍDOS DO ZERO a cada chamada, e não remendados:
        um `update()` deixaria vivo o botão que a escolha ANTERIOR tinha posto e
        a nova tirou — o perfil trocaria de dono e o botão continuaria clicando.

        UM BOTÃO ESTÁ EM UM MAPA SÓ. `BTN_*` é do mouse; `KEY_*` do d-pad e do
        tap continuam vindo do padrão, porque quem os troca é o teclado virtual
        (a segunda sacola do `resolver`), e não este device. Pôr a mesma tecla
        nos dois faria o botão emitir duas vezes.

        `calados` É A SEGUNDA SACOLA QUE FALTAVA — 06/09/2026, ONDA3-MOTOR-01, e
        ela nasce de um defeito medido: `do_mouse` **não distingue "não é do
        mouse" de "foi calado"**. Um botão que ela pôs em `— Nada —` não entra
        em `do_mouse` (o `resolver()` o pula de propósito), logo a subtração
        acima não o alcançava e ele **voltava ao valor de fábrica**. Escapavam
        SEIS dos vinte e dois — as quatro direções do d-pad, o Círculo e o
        Quadrado —, e os outros dezesseis calavam porque os mapas que os
        atendem são SUBSTITUÍDOS inteiros.

        Ela escolhia `— Nada —`, a tela confirmava, e o botão continuava fazendo
        o que fazia: perda silenciosa de escolha do usuário. Quem monta a sacola é
        `core/acoes_de_botao.botoes_calados()`; `None` aqui quer dizer "ninguém
        informou", e é o contrato de antes byte a byte.
        """
        if do_mouse is None:
            self._mapa_botoes = dict(BUTTON_TO_UINPUT)
            self._mapa_dpad = dict(DPAD_TO_KEY)
            self._mapa_tap = dict(EDGE_KEY_MAP)
            return
        mudos = frozenset(calados or ())
        self._mapa_botoes = dict(do_mouse)
        self._mapa_dpad = {b: k for b, k in DPAD_TO_KEY.items()
                           if b not in do_mouse and b not in mudos}
        self._mapa_tap = {b: k for b, k in EDGE_KEY_MAP.items()
                          if b not in do_mouse and b not in mudos}

    def dispatch(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
        buttons: frozenset[str],
        now: float | None = None,
    ) -> None:
        """Aplica um snapshot de estado no device virtual.

        Args:
            lx, ly: stick esquerdo (0-255) — vira REL_X/REL_Y com deadzone.
            rx, ry: stick direito (0-255) — vira REL_WHEEL/REL_HWHEEL.
            l2, r2: trigger analógico (0-255) — acima de TRIGGER_PRESS_THRESHOLD
                    conta como botão pressionado (L2→cross, R2→triangle).
            buttons: conjunto canônico Hefesto - DualSense4Unix pressionado agora.
            now: timestamp monotônico opcional (injetável em testes). Default
                 usa `time.monotonic()`.
        """
        if self._device is None or self._uinput_mod is None:
            return
        if now is None:
            now = time.monotonic()

        emulated = self._resolve_emulated_set(buttons, l2, r2)
        self._emit_buttons(emulated)
        self._emit_dpad(buttons)
        self._emit_edge_keys(buttons)
        self._emit_move(lx, ly)
        self._emit_scroll(rx, ry, now)
        self._last_buttons_emulated = emulated
        self._prev_edge_keys = frozenset(b for b in buttons if b in self._mapa_tap)

    def _resolve_emulated_set(
        self, buttons: frozenset[str], l2: int, r2: int
    ) -> frozenset[str]:
        """Converte botões Hefesto - DualSense4Unix + triggers analógicos em set canônico emulado.

        L2 analógico acima de TRIGGER_PRESS_THRESHOLD injeta 'cross' virtual.
        R2 análogo injeta 'triangle'. Se usuário também apertou cross/triangle
        físicos, o set continua idempotente (frozenset absorve duplicatas).
        """
        resolved = set(buttons)
        if l2 >= TRIGGER_PRESS_THRESHOLD:
            resolved.add("cross")
        if r2 >= TRIGGER_PRESS_THRESHOLD:
            resolved.add("triangle")
        return frozenset(resolved)

    def _emit_buttons(self, emulated: frozenset[str]) -> None:
        """Edge-triggered press/release dos botões do mouse."""
        u = self._uinput_mod
        relevant_now = {b for b in emulated if b in self._mapa_botoes}
        relevant_last = {b for b in self._last_buttons_emulated if b in self._mapa_botoes}

        newly_pressed = relevant_now - relevant_last
        newly_released = relevant_last - relevant_now

        for name in newly_pressed:
            ev = getattr(u, self._mapa_botoes[name], None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for name in newly_released:
            ev = getattr(u, self._mapa_botoes[name], None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        if newly_pressed or newly_released:
            self._device.syn()

    def _emit_dpad(self, buttons: frozenset[str]) -> None:
        """Edge-triggered D-pad → KEY_UP/DOWN/LEFT/RIGHT."""
        u = self._uinput_mod
        dpad_now = {b for b in buttons if b in self._mapa_dpad}
        dpad_last = {b for b in self._last_buttons_emulated if b in self._mapa_dpad}

        newly_pressed = dpad_now - dpad_last
        newly_released = dpad_last - dpad_now

        for name in newly_pressed:
            ev = getattr(u, self._mapa_dpad[name], None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for name in newly_released:
            ev = getattr(u, self._mapa_dpad[name], None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        if newly_pressed or newly_released:
            self._device.syn()

    def _emit_edge_keys(self, buttons: frozenset[str]) -> None:
        """Circle/Square como tap edge-triggered (FEAT-MOUSE-02).

        Em cada transição False→True emite press+release imediatos da tecla
        mapeada (KEY_ENTER/KEY_ESC). Hold do botão NÃO repete — só uma borda
        de subida gera nova emissão.
        """
        u = self._uinput_mod
        edge_now = {b for b in buttons if b in self._mapa_tap}
        newly_pressed = edge_now - self._prev_edge_keys

        if not newly_pressed:
            return

        for name in newly_pressed:
            ev = getattr(u, self._mapa_tap[name], None)
            if ev is None:
                continue
            self._device.emit(ev, 1, syn=False)
            self._device.emit(ev, 0, syn=False)
        self._device.syn()

    def _emit_move(self, lx: int, ly: int) -> None:
        """Stick esquerdo → REL_X/REL_Y (pipeline float, FEAT-MOUSE-CURSOR-FEEL-01).

        Integra a velocidade-alvo (px/s de `_compute_move_px_per_sec`) pelo
        período do tick (`1/poll_hz`) com carry fracionário: emite a parte
        inteira e leva o resto ao próximo tick. `int()` trunca em direção ao
        zero — simétrico para deltas negativos. Dentro da deadzone os carries
        são zerados para o resíduo não vazar como drift ao voltar a mover.
        """
        vx, vy = _compute_move_px_per_sec(lx, ly, self.mouse_speed)
        if vx == 0.0 and vy == 0.0:
            self._stick_carry_x = 0.0
            self._stick_carry_y = 0.0
            return
        period = 1.0 / max(1, self.poll_hz)
        self._stick_carry_x += vx * period
        self._stick_carry_y += vy * period
        ix = int(self._stick_carry_x)
        iy = int(self._stick_carry_y)
        self._stick_carry_x -= ix
        self._stick_carry_y -= iy
        if ix == 0 and iy == 0:
            return
        u = self._uinput_mod
        if ix != 0:
            self._device.emit(u.REL_X, ix, syn=False)
        if iy != 0:
            self._device.emit(u.REL_Y, iy, syn=False)
        self._device.syn()

    def _emit_scroll(self, rx: int, ry: int, now: float) -> None:
        """Stick direito → REL_WHEEL/REL_HWHEEL com deadzone e rate-limit 50ms."""
        step_v = _compute_scroll_step(ry)
        step_h = _compute_scroll_step(rx)
        if step_v == 0 and step_h == 0:
            return
        if (now - self._last_scroll_at) < SCROLL_RATE_LIMIT_SEC:
            return

        u = self._uinput_mod
        if step_v != 0:
            self._device.emit(u.REL_WHEEL, -step_v * self.scroll_speed, syn=False)
        if step_h != 0:
            self._device.emit(u.REL_HWHEEL, step_h * self.scroll_speed, syn=False)
        self._device.syn()
        self._last_scroll_at = now

    def emit_touchpad_move(self, raw_dx: int, raw_dy: int) -> None:
        """Move o cursor a partir de um delta bruto do touchpad (B4)."""
        if self._device is None or self._uinput_mod is None:
            return
        if raw_dx == 0 and raw_dy == 0:
            return
        factor = TOUCHPAD_SENSITIVITY * (self.mouse_speed / DEFAULT_MOUSE_SPEED)
        self._tp_carry_x += raw_dx * factor
        self._tp_carry_y += raw_dy * factor
        ix = int(self._tp_carry_x)
        iy = int(self._tp_carry_y)
        self._tp_carry_x -= ix
        self._tp_carry_y -= iy
        if ix == 0 and iy == 0:
            return
        u = self._uinput_mod
        if ix != 0:
            self._device.emit(u.REL_X, ix, syn=False)
        if iy != 0:
            self._device.emit(u.REL_Y, iy, syn=False)
        self._device.syn()

    def emit_gyro_move(self, px_x: float, px_y: float) -> None:
        """Move o cursor a partir de um deslocamento já em PIXELS float."""
        if self._device is None or self._uinput_mod is None:
            return
        if px_x == 0.0 and px_y == 0.0:
            return
        self._giro_carry_x += px_x
        self._giro_carry_y += px_y
        ix = int(self._giro_carry_x)
        iy = int(self._giro_carry_y)
        self._giro_carry_x -= ix
        self._giro_carry_y -= iy
        if ix == 0 and iy == 0:
            return
        u = self._uinput_mod
        if ix != 0:
            self._device.emit(u.REL_X, ix, syn=False)
        if iy != 0:
            self._device.emit(u.REL_Y, iy, syn=False)
        self._device.syn()


NOME_DO_CURSOR_DO_TOQUE = "Hefesto - DualSense4Unix Touch Cursor"

CLIQUE_SEM_NOTICIA_S = 0.5


@dataclass
class CursorDoToque:
    """O ponteiro que o touchpad move pelo Hefesto com o controle virtual de pé.

    A resposta de 28/09 (~16h50) pôs «o touchpad move o cursor» entre os
    arranjos por perfil de jogo. Na Navegação o cursor é o do mouse emulado;
    no modo DualSense e no Xbox não há mouse emulado (a exclusão mútua), e o
    arranjo precisa de um nó próprio, mínimo: movimento relativo e o botão
    esquerdo, que é o clique do touchpad. Quem o cria é o daemon
    (`Daemon._garantir_cursor_do_toque`); quem o move é o tique
    (`gamepad.aplicar_o_toque`), já em pixels float — o carry sub-pixel é
    daqui, como no `emit_gyro_move`.

    O CLIQUE É DA MESA: duas peças no cursor dividem o mesmo botão, e ele fica
    apertado enquanto qualquer uma o segurar — e der notícia
    (:data:`CLIQUE_SEM_NOTICIA_S`, :meth:`conferir`).
    """

    name: str = NOME_DO_CURSOR_DO_TOQUE
    _device: Any = None
    _uinput_mod: Any = None
    _carry_x: float = 0.0
    _carry_y: float = 0.0
    _clicando: dict[str, float] = field(default_factory=dict)
    _botao: bool = False

    def start(self) -> bool:
        """Cria o nó. False sem `/dev/uinput` ou sem o módulo — o tique segue."""
        if self._device is not None:
            return True
        try:
            import uinput
        except ImportError:
            logger.warning("python-uinput não instalado — cursor do toque indisponível")
            return False
        try:
            self._device = uinput.Device(
                [uinput.REL_X, uinput.REL_Y, uinput.BTN_LEFT], name=self.name
            )
            self._uinput_mod = uinput
        except Exception as exc:
            logger.warning("cursor_do_toque_create_failed", err=str(exc))
            return False
        logger.info("cursor_do_toque_criado", name=self.name)
        return True

    def stop(self) -> None:
        """Solta o botão, se estava apertado, e destrói o nó. Idempotente."""
        if self._device is None:
            return
        if self._botao and self._uinput_mod is not None:
            with contextlib.suppress(Exception):
                self._device.emit(self._uinput_mod.BTN_LEFT, 0)
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._uinput_mod = None
        self._carry_x = 0.0
        self._carry_y = 0.0
        self._clicando = {}
        self._botao = False

    def mover(self, px_x: float, px_y: float) -> None:
        """Anda o cursor em pixels float, guardando o resto sub-pixel."""
        if self._device is None or self._uinput_mod is None:
            return
        self._carry_x += px_x
        self._carry_y += px_y
        ix = int(self._carry_x)
        iy = int(self._carry_y)
        self._carry_x -= ix
        self._carry_y -= iy
        if ix == 0 and iy == 0:
            return
        u = self._uinput_mod
        if ix != 0:
            self._device.emit(u.REL_X, ix, syn=False)
        if iy != 0:
            self._device.emit(u.REL_Y, iy, syn=False)
        self._device.syn()

    def clicar(self, peca: str, apertado: bool, agora: float | None = None) -> None:
        """O clique do touchpad da `peca`; o botão só muda na borda da mesa."""
        agora = time.monotonic() if agora is None else agora
        if apertado:
            self._clicando[peca] = agora
        else:
            self._clicando.pop(peca, None)
        self.conferir(agora)

    def conferir(self, agora: float | None = None) -> None:
        """Solta o clique de quem parou de dar notícia, e acerta o botão."""
        agora = time.monotonic() if agora is None else agora
        if self._clicando:
            self._clicando = {
                p: t for p, t in self._clicando.items() if agora - t <= CLIQUE_SEM_NOTICIA_S
            }
        querido = bool(self._clicando)
        if querido == self._botao:
            return
        if self._device is not None and self._uinput_mod is not None:
            self._device.emit(self._uinput_mod.BTN_LEFT, 1 if querido else 0)
        self._botao = querido


__all__ = [
    "BUTTON_TO_UINPUT",
    "CLIQUE_SEM_NOTICIA_S",
    "DEFAULT_MOUSE_SPEED",
    "DEFAULT_POLL_HZ",
    "DEFAULT_SCROLL_SPEED",
    "DEVICE_NAME",
    "DPAD_TO_KEY",
    "EDGE_KEY_MAP",
    "MOUSE_EXPO",
    "MOUSE_PX_PER_SEC_STEP",
    "MOVE_DEADZONE",
    "NOME_DO_CURSOR_DO_TOQUE",
    "SCROLL_DEADZONE",
    "SCROLL_RATE_LIMIT_SEC",
    "TOUCHPAD_SENSITIVITY",
    "TRIGGER_PRESS_THRESHOLD",
    "CursorDoToque",
    "UinputMouseDevice",
    "_compute_move_px_per_sec",
    "_compute_scroll_step",
]

