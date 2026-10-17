"""Emulação de mouse+teclado via python-uinput a partir do DualSense (FEAT-MOUSE-01/02).

Cria um device virtual uinput expondo:
  - BTN_LEFT, BTN_RIGHT, BTN_MIDDLE
  - REL_X, REL_Y (movimento) e REL_WHEEL, REL_HWHEEL (rolagem)
  - KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT (D-pad → setas)
  - KEY_ENTER, KEY_ESC (Circle → Enter, Square → Esc — FEAT-MOUSE-02)

Mapeamento canônico (FEAT-MOUSE-01/02, decidido pelo usuário):

| DualSense                | Saída emulada          | evdev code    |
|--------------------------|------------------------|---------------|
| Cross (X) e L2           | Botão esquerdo         | BTN_LEFT      |
| Triangle () e R2        | Botão direito          | BTN_RIGHT     |
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
    guardado na instância POR CÓDIGO (`_codigos_apertados`, `_setas_apertadas`).
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

#: O gatilho conta como apertado a partir daqui, em fração do curso. UM DONO: o
#: mouse emulado e a tabela que age junto com o jogo leem o mesmo número. É o
#: 0,35 que a ponte provisória do GON mediu; os 64/255 de antes (~0,25) clicavam
#: com o dedo apenas encostado.
LIMIAR_DO_GATILHO = 0.35
TRIGGER_PRESS_THRESHOLD = math.ceil(LIMIAR_DO_GATILHO * 255)

#: As duas linhas dos analógicos e os dois tokens que as ligam. Moram aqui e não em
#: `core/acoes_de_botao` porque o device precisa delas e o módulo da tabela o importa.
EIXO_ESQUERDO = "l3_direcao"
EIXO_DIREITO = "r3_direcao"
TOKEN_CURSOR = "__CURSOR__"
TOKEN_ROLAGEM = "__ROLAGEM__"

MOUSE_EXPO = 1.6
MOUSE_PX_PER_SEC_STEP = 125.0
# daemon). Os callsites reais passam `config.poll_hz`.
DEFAULT_POLL_HZ = 60

TOUCHPAD_SENSITIVITY = 0.45

BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_LEFT",
    "triangle": "BTN_RIGHT",
    "r3": "BTN_MIDDLE",
    # Os gatilhos são linha própria, e não mais espelho do Cruz e do Triângulo: o
    # perfil escolhe o que cada um faz (um botão do mouse ou uma tecla).
    "l2": "BTN_LEFT",
    "r2": "BTN_RIGHT",
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


def gatilho_apertado(bruto: int) -> bool:
    """O gatilho de curso `bruto` (0-255) conta como apertado? O DONO da pergunta."""
    return bruto >= TRIGGER_PRESS_THRESHOLD


#: O gatilho escolhido como botão de precisão vale a partir da metade do curso.
PRECISAO_DO_GATILHO = 127
#: Sem notícia do controle por tanto tempo, o clique travado solta na volta (queda do controle).
TRAVA_SEM_NOTICIA_S = 1.0

_ATRIBUTO_DO_AJUSTE = "_ajuste_do_cursor_da_mesa"


@dataclass(frozen=True, slots=True)
class AjusteDoCursor:
    """O que o perfil muda no cursor. O padrão é o de hoje: zona morta 20, curva 1,6, nada mais."""

    zona_morta: int = MOVE_DEADZONE
    curva: float = MOUSE_EXPO
    precisao_botao: str | None = None
    precisao: float = 0.3
    permanencia_s: float = 0.0
    clique_travado: str | None = None

    @property
    def algum(self) -> bool:
        return (
            self.zona_morta != MOVE_DEADZONE or self.curva != MOUSE_EXPO
            or self.precisao_botao is not None or self.permanencia_s > 0
            or self.clique_travado is not None
        )


def montar_o_ajuste(secao: Any) -> AjusteDoCursor | None:
    """A seção `cursor` do perfil como ajuste. ``None`` = o cursor de sempre."""
    if secao is None:
        return None
    padrao = AjusteDoCursor()
    ajuste = AjusteDoCursor(
        zona_morta=int(getattr(secao, "zona_morta", padrao.zona_morta)),
        curva=float(getattr(secao, "curva", padrao.curva)),
        precisao_botao=getattr(secao, "precisao_botao", None) or None,
        precisao=int(getattr(secao, "precisao", 30)) / 100.0,  # (noqa-acento) identificador ASCII
        permanencia_s=int(getattr(secao, "permanencia_ms", 0) or 0) / 1000.0,
        clique_travado=getattr(secao, "clique_travado", None) or None,
    )
    return ajuste if ajuste.algum else None


def definir_ajuste_ativo(dono: Any, ajuste: AjusteDoCursor | None) -> None:
    """Guarda o ajuste ATIVO no dono (o ``StateStore``); cada ativação de perfil conta uma época."""
    if dono is None:
        return
    _, epoca = ajuste_ativo(dono)
    setattr(dono, _ATRIBUTO_DO_AJUSTE, (ajuste, epoca + 1))


def ajuste_ativo(dono: Any) -> tuple[AjusteDoCursor | None, int]:
    """O ajuste que vale AGORA e a época dele (muda a cada ativação de perfil)."""
    valor = getattr(dono, _ATRIBUTO_DO_AJUSTE, None)
    if isinstance(valor, tuple) and len(valor) == 2:
        return valor
    return None, 0


def _build_capabilities() -> list[tuple[Any, ...]]:
    """Lista de eventos que o uinput device expõe. Import lazy.

    `REL_X`/`REL_Y` ficam SEMPRE declarados, mesmo quando nenhuma linha move o
    cursor: sem eles o udev não classifica o nó como mouse e o clique não chega a
    lugar nenhum. Declarar não é emitir — quem decide emitir é :meth:`UinputMouseDevice.dispatch`.
    """
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


def _compute_move_px_per_sec(
    lx: int, ly: int, speed: int,
    zona_morta: int = MOVE_DEADZONE, expoente: float = MOUSE_EXPO,
) -> tuple[float, float]:
    """Converte o stick esquerdo (0-255 por eixo) em velocidade-alvo (px/s)."""
    nx = (lx - STICK_CENTER) / STICK_CENTER
    ny = (ly - STICK_CENTER) / STICK_CENTER
    mag = math.hypot(nx, ny)
    dz = zona_morta / STICK_CENTER
    if mag <= dz:
        return 0.0, 0.0
    m = min(1.0, (mag - dz) / (1.0 - dz))
    curved = m ** expoente
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
    # Os códigos `BTN_*` que ESTE device mantém apertados. A borda é por código, e
    # não por botão: dois botões (a Cruz e o L2) podem dar o mesmo clique, e o
    # clique só solta quando o último deles solta.
    _codigos_apertados: frozenset[str] = field(default_factory=frozenset)
    # As setas `KEY_*` que ESTE device mantém apertadas, pela mesma razão: a troca
    # de tabela as solta, e a borda seguinte pergunta pelo código, não pelo mapa.
    _setas_apertadas: frozenset[str] = field(default_factory=frozenset)
    # O cursor e a rolagem só andam se a linha do analógico escolher o próprio token.
    _cursor_ligado: bool = True
    _rolagem_ligada: bool = True
    _last_scroll_at: float = -math.inf
    _prev_edge_keys: frozenset[str] = field(default_factory=frozenset)
    _tp_carry_x: float = 0.0
    _tp_carry_y: float = 0.0
    _giro_carry_x: float = 0.0
    _giro_carry_y: float = 0.0
    _stick_carry_x: float = 0.0
    _stick_carry_y: float = 0.0
    # O ajuste de acessibilidade do cursor (None = o de sempre) e o que ele guarda entre tiques.
    _ajuste: AjusteDoCursor | None = None
    _epoca: int = 0
    _fator: float = 1.0
    _preso: bool = False
    _travador_antes: bool = False
    _codigos_reais: frozenset[str] = field(default_factory=frozenset)
    _andou: bool = False
    _ultimo_movimento: float = -math.inf
    _ultimo_dispatch: float = -math.inf

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
        self._codigos_apertados = frozenset()
        self._setas_apertadas = frozenset()
        self._last_scroll_at = -math.inf
        self._prev_edge_keys = frozenset()
        self._tp_carry_x = 0.0
        self._tp_carry_y = 0.0
        self._giro_carry_x = 0.0
        self._giro_carry_y = 0.0
        self._stick_carry_x = 0.0
        self._stick_carry_y = 0.0
        self._preso = False
        self._travador_antes = False
        self._codigos_reais = frozenset()
        self._andou = False
        self._fator = 1.0

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

    def definir_ajuste(self, ajuste: AjusteDoCursor | None, epoca: int = 0) -> None:
        """Troca o ajuste do cursor. Cada ativação de perfil (época nova) solta o clique travado."""
        if ajuste == self._ajuste and epoca == self._epoca:
            return
        self._ajuste = ajuste
        self._epoca = epoca
        self._fator = 1.0
        self._andou = False
        self._travador_antes = False
        self.soltar_o_clique_travado()

    def soltar_o_clique_travado(self) -> None:
        """Solta o clique que o travador prendeu (a soltura é garantida: perfil, jogo, queda)."""
        if not self._preso:
            return
        self._preso = False
        restante = self._codigos_reais
        soltar = self._codigos_apertados - restante
        self._codigos_apertados = restante
        if self._device is None or self._uinput_mod is None or not soltar:
            return
        for codigo in sorted(soltar):
            ev = getattr(self._uinput_mod, codigo, None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)
        self._device.syn()

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
        self._soltar_o_que_segura()
        self._stick_carry_x = 0.0
        self._stick_carry_y = 0.0
        if do_mouse is None:
            self._mapa_botoes = dict(BUTTON_TO_UINPUT)
            self._mapa_dpad = dict(DPAD_TO_KEY)
            self._mapa_tap = dict(EDGE_KEY_MAP)
            self._cursor_ligado = True
            self._rolagem_ligada = True
            return
        mudos = frozenset(calados or ())
        # AS DUAS LINHAS DOS ANALÓGICOS NÃO SÃO BOTÃO: o token delas liga o eixo.
        # Linha ausente é o de fábrica (ligado); `— Nada —` chega por `calados`;
        # qualquer outro token que não seja o próprio eixo desliga.
        self._cursor_ligado = (
            EIXO_ESQUERDO not in mudos
            and do_mouse.get(EIXO_ESQUERDO, TOKEN_CURSOR) == TOKEN_CURSOR)
        self._rolagem_ligada = (
            EIXO_DIREITO not in mudos
            and do_mouse.get(EIXO_DIREITO, TOKEN_ROLAGEM) == TOKEN_ROLAGEM)
        eixos = (EIXO_ESQUERDO, EIXO_DIREITO)
        self._mapa_botoes = {b: t for b, t in do_mouse.items() if b not in eixos}
        self._mapa_dpad = {b: k for b, k in DPAD_TO_KEY.items()
                           if b not in do_mouse and b not in mudos}
        self._mapa_tap = {b: k for b, k in EDGE_KEY_MAP.items()
                          if b not in do_mouse and b not in mudos}

    def _soltar_o_que_segura(self) -> None:
        """Solta os cliques e as setas que a tabela ANTERIOR mantinha: ela deixou de valer."""
        segurados = self._codigos_apertados | self._setas_apertadas
        self._codigos_apertados = frozenset()
        self._codigos_reais = frozenset()
        self._setas_apertadas = frozenset()
        self._preso = False
        if self._device is None or self._uinput_mod is None or not segurados:
            return
        for codigo in sorted(segurados):
            ev = getattr(self._uinput_mod, codigo, None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)
        self._device.syn()

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
            l2, r2: trigger analógico (0-255) — a partir de TRIGGER_PRESS_THRESHOLD
                    o botão `l2`/`r2` conta como apertado, e a LINHA dele
                    na tabela diz o que sai (cada gatilho tem a sua).
            buttons: conjunto canônico Hefesto - DualSense4Unix pressionado agora.
            now: timestamp monotônico opcional (injetável em testes). Default
                 usa `time.monotonic()`.
        """
        if self._device is None or self._uinput_mod is None:
            return
        if now is None:
            now = time.monotonic()

        emulated = self._resolve_emulated_set(buttons, l2, r2)
        ajuste = self._ajuste
        if ajuste is not None:
            buttons, emulated = self._ajudar(ajuste, buttons, emulated, l2, r2, now)
        self._emit_buttons(emulated)
        self._emit_dpad(buttons)
        self._emit_edge_keys(buttons)
        if self._cursor_ligado:
            self._emit_move(lx, ly, now)
        if self._rolagem_ligada:
            self._emit_scroll(rx, ry, now)
        self._prev_edge_keys = frozenset(b for b in buttons if b in self._mapa_tap)
        if ajuste is not None and ajuste.permanencia_s > 0:
            self._conferir_a_permanencia(ajuste, now)

    def _ajudar(
        self, ajuste: AjusteDoCursor, buttons: frozenset[str], emulated: frozenset[str],
        l2: int, r2: int, now: float,
    ) -> tuple[frozenset[str], frozenset[str]]:
        """A precisão e o clique travado deste tique. Devolve os botões que SOBRAM para a tabela.

        O botão da precisão e o do travador são do cursor: um botão tem um modo só, então
        eles não clicam nem viram seta ao mesmo tempo.
        """
        if self._preso and (now - self._ultimo_dispatch) > TRAVA_SEM_NOTICIA_S:
            self.soltar_o_clique_travado()
        self._ultimo_dispatch = now
        bruto = {"l2": l2, "r2": r2}
        precisao = ajuste.precisao_botao
        if precisao is None:
            self._fator = 1.0
        else:
            apertado = (
                bruto[precisao] >= PRECISAO_DO_GATILHO if precisao in bruto
                else precisao in buttons)
            self._fator = ajuste.precisao if apertado else 1.0
        travador = ajuste.clique_travado
        if travador is not None:
            apertado = (
                gatilho_apertado(bruto[travador]) if travador in bruto else travador in buttons)
            if apertado and not self._travador_antes:
                self._preso = not self._preso
            self._travador_antes = apertado
        consumidos = frozenset(b for b in (precisao, travador) if b is not None)
        return buttons - consumidos, emulated - consumidos

    def _notou_movimento(self, now: float) -> None:
        """O cursor foi pedido a andar neste instante (a permanência conta daqui)."""
        self._andou = True
        self._ultimo_movimento = now

    def _conferir_a_permanencia(self, ajuste: AjusteDoCursor, now: float) -> None:
        """Parado por `permanencia_s` depois de andar: um clique; outro só andando de novo."""
        if not self._andou or (now - self._ultimo_movimento) < ajuste.permanencia_s:
            return
        self._andou = False
        if "BTN_LEFT" in self._codigos_apertados or self._device is None:
            return
        u = self._uinput_mod
        self._device.emit(u.BTN_LEFT, 1)
        self._device.emit(u.BTN_LEFT, 0)

    def _resolve_emulated_set(
        self, buttons: frozenset[str], l2: int, r2: int
    ) -> frozenset[str]:
        """Os botões apertados agora, com os gatilhos analógicos já viraram `l2`/`r2`.

        Cada gatilho é uma LINHA própria da tabela (`l2`, `r2`), sem espelho no
        Cruz ou no Triângulo: o que ele faz é o que o perfil escolheu para ele.
        """
        resolved = set(buttons)
        if gatilho_apertado(l2):
            resolved.add("l2")
        if gatilho_apertado(r2):
            resolved.add("r2")
        return frozenset(resolved)

    def _emit_buttons(self, emulated: frozenset[str]) -> None:
        """Edge-triggered press/release dos botões do mouse, POR CÓDIGO `BTN_*`."""
        u = self._uinput_mod
        reais = frozenset(
            self._mapa_botoes[b] for b in emulated if b in self._mapa_botoes)
        self._codigos_reais = reais
        agora = reais | {"BTN_LEFT"} if self._preso else reais
        antes = self._codigos_apertados

        newly_pressed = agora - antes
        newly_released = antes - agora

        for codigo in sorted(newly_pressed):
            ev = getattr(u, codigo, None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for codigo in sorted(newly_released):
            ev = getattr(u, codigo, None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        self._codigos_apertados = agora
        if newly_pressed or newly_released:
            self._device.syn()

    def _emit_dpad(self, buttons: frozenset[str]) -> None:
        """Edge-triggered D-pad → KEY_UP/DOWN/LEFT/RIGHT, POR CÓDIGO `KEY_*`."""
        u = self._uinput_mod
        agora = frozenset(self._mapa_dpad[b] for b in buttons if b in self._mapa_dpad)
        antes = self._setas_apertadas

        newly_pressed = agora - antes
        newly_released = antes - agora

        for codigo in sorted(newly_pressed):
            ev = getattr(u, codigo, None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for codigo in sorted(newly_released):
            ev = getattr(u, codigo, None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        self._setas_apertadas = agora
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

    def _emit_move(self, lx: int, ly: int, now: float | None = None) -> None:
        """Stick esquerdo → REL_X/REL_Y (pipeline float, FEAT-MOUSE-CURSOR-FEEL-01).

        Integra a velocidade-alvo (px/s de `_compute_move_px_per_sec`) pelo
        período do tick (`1/poll_hz`) com carry fracionário: emite a parte
        inteira e leva o resto ao próximo tick. `int()` trunca em direção ao
        zero — simétrico para deltas negativos. Dentro da deadzone os carries
        são zerados para o resíduo não vazar como drift ao voltar a mover.
        """
        ajuste = self._ajuste
        if ajuste is None:
            vx, vy = _compute_move_px_per_sec(lx, ly, self.mouse_speed)
        else:
            vx, vy = _compute_move_px_per_sec(
                lx, ly, self.mouse_speed, ajuste.zona_morta, ajuste.curva)
        if vx == 0.0 and vy == 0.0:
            self._stick_carry_x = 0.0
            self._stick_carry_y = 0.0
            return
        if ajuste is not None:
            self._notou_movimento(time.monotonic() if now is None else now)
        period = 1.0 / max(1, self.poll_hz)
        self._stick_carry_x += vx * period * self._fator
        self._stick_carry_y += vy * period * self._fator
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
        if (now - self._last_scroll_at) < SCROLL_RATE_LIMIT_SEC / self._fator:
            return

        u = self._uinput_mod
        if step_v != 0:
            self._device.emit(u.REL_WHEEL, -step_v * self.scroll_speed, syn=False)
        if step_h != 0:
            self._device.emit(u.REL_HWHEEL, step_h * self.scroll_speed, syn=False)
        self._device.syn()
        self._last_scroll_at = now

    def emit_touchpad_move(self, raw_dx: int, raw_dy: int, now: float | None = None) -> None:
        """Move o cursor a partir de um delta bruto do touchpad (B4)."""
        if self._device is None or self._uinput_mod is None:
            return
        if raw_dx == 0 and raw_dy == 0:
            return
        if self._ajuste is not None:
            self._notou_movimento(time.monotonic() if now is None else now)
        factor = TOUCHPAD_SENSITIVITY * (self.mouse_speed / DEFAULT_MOUSE_SPEED) * self._fator
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

    def emit_gyro_move(self, px_x: float, px_y: float, now: float | None = None) -> None:
        """Move o cursor a partir de um deslocamento já em PIXELS float."""
        if self._device is None or self._uinput_mod is None:
            return
        if px_x == 0.0 and px_y == 0.0:
            return
        if self._ajuste is not None:
            self._notou_movimento(time.monotonic() if now is None else now)
        self._giro_carry_x += px_x * self._fator
        self._giro_carry_y += px_y * self._fator
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
    "EIXO_DIREITO",
    "EIXO_ESQUERDO",
    "LIMIAR_DO_GATILHO",
    "MOUSE_EXPO",
    "MOUSE_PX_PER_SEC_STEP",
    "MOVE_DEADZONE",
    "NOME_DO_CURSOR_DO_TOQUE",
    "PRECISAO_DO_GATILHO",
    "SCROLL_DEADZONE",
    "SCROLL_RATE_LIMIT_SEC",
    "TOKEN_CURSOR",
    "TOKEN_ROLAGEM",
    "TOUCHPAD_SENSITIVITY",
    "TRAVA_SEM_NOTICIA_S",
    "TRIGGER_PRESS_THRESHOLD",
    "AjusteDoCursor",
    "CursorDoToque",
    "UinputMouseDevice",
    "_compute_move_px_per_sec",
    "_compute_scroll_step",
    "ajuste_ativo",
    "definir_ajuste_ativo",
    "gatilho_apertado",
    "montar_o_ajuste",
]

