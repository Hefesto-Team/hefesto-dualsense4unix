"""Contrato comum dos gamepads virtuais + escolha do backend (SPRINT-UHID-VPAD-01).

Existem dois backends de vpad, e os call sites (`subsystems/gamepad.py` para o P1,
`subsystems/coop.py` para os secundários) não devem saber em qual estão:

  - `UinputGamepad` (/dev/uinput): só evdev. É o que faz a máscara **Xbox 360**,
    e é o caminho histórico — intacto.
  - `UhidDualSense` (/dev/uhid): device **HID** de verdade. O `hid_playstation`
    faz bind nele e o vpad ganha hidraw + lightbar + player-LED + motion sensors
    + touchpad. É o que faz a máscara **DualSense finalmente vibrar** no jogo (com
    uinput ela é evdev-only, o SDL usa o driver PS5, procura o hidraw, não acha, e
    o rumble morre — a razão de a máscara Xbox ter virado obrigatória).

`VirtualPad` é a interface que os dois cumprem; `make_virtual_pad` decide qual usar
e **já devolve o pad startado** — é ali que mora o fallback, num lugar só.

Por que o fallback vive na factory
----------------------------------
O caminho uhid tem três pontos de falha (nó ausente/sem regra udev, CREATE2
recusado, `hid_playstation` que não faz bind) e todos significam a mesma coisa
para o chamador: **use o uinput**. Espalhar isso pelos call sites daria uma
versão diferente do fallback em cada um. Cada motivo é logado (não silenciado):
"caiu no uinput" sem dizer por quê é um bug que a usuária sente no jogo e
ninguém consegue diagnosticar.

Blueprint canônico embutido (VPAD-03 / BT-01)
---------------------------------------------
O vpad uhid usa SEMPRE o blueprint sintético de `uhid_blueprint.py` — nenhuma
leitura do controle físico no caminho de criação. O modo de falha "controle
físico sem hidraw legível" morreu por construção: era ele que, em BT com o
controle ocioso (GET_REPORT estourando o timeout de 5 s do hidp com EIO),
derrubava o vpad para uinput `054c:0ce6` — indistinguível do físico e alvo da
launch option `IGNORE_DEVICES` persistida na Steam (jogo com zero controles).
O vpad sobe uhid Edge até sem controle conectado (boot antes do connect).

`allow_uhid=False` é o veto explícito do chamador (VPAD-08): o daemon FAKE
(`run.sh --fake`, usado em smoke na máquina da usuária) não pode registrar um
DualSense Edge REAL no kernel — a Steam enxergaria um controle fantasma.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

#: Timeout do `wait_for_bind`. O probe do `hid_playstation` faz várias idas e
#: voltas (GET_REPORT 0x09/0x20/0x05) antes do UHID_START.
#:
#: Medido ao vivo (6 execuções): o START chega em **2,3 ms** (pior caso 2,4 ms) —
#: 0,5 s são 200x de folga. Importa porque o `wait_for_bind` roda DENTRO do poll
#: loop (o co-op promove jogador em `sync`/`forward_all`): no caminho de falha o
#: timeout inteiro vira input congelado do P1. Com os 2,0 s originais um uhid que
#: não subisse travava o controle por 2 segundos.
UHID_BIND_TIMEOUT_S = 0.5


@runtime_checkable
class VirtualPad(Protocol):
    """O que o daemon usa de um gamepad virtual, seja ele uinput ou uhid.

    Membros só-leitura de propósito: o daemon lê `flavor`/`ff_*` para a GUI e o
    doctor, mas quem define a máscara é a factory, na criação.
    """

    @property
    def flavor(self) -> str:
        """Máscara que o jogo vê: "dualsense" ou "xbox"."""
        ...

    @property
    def backend(self) -> str:
        """"uinput" (evdev, máscara Xbox / fallback) ou "uhid" (DualSense HID real,
        Edge 0x0DF2). O botão de Launch Options escolhe a variante por aqui: só o
        "uhid" tem PID próprio e pode ser desduplicado por IGNORE_DEVICES."""
        ...

    @property
    def ff_supported(self) -> bool:
        """True quando o rumble do jogo tem por onde chegar até nós."""
        ...

    @property
    def ff_play_count(self) -> int:
        """Nº de pedidos de rumble que o JOGO fez neste vpad (diagnóstico)."""
        ...

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) 0-255 entregue ao `rumble_sink`."""
        ...

    def start(self) -> bool: ...

    def stop(self) -> None: ...

    def is_active(self) -> bool: ...

    def forward_analog(
        self, *, lx: int, ly: int, rx: int, ry: int, l2: int, r2: int
    ) -> None: ...

    def forward_buttons(self, pressed: frozenset[str]) -> None: ...

    def pump_ff(self) -> None: ...


def make_virtual_pad(
    flavor: str | None,
    *,
    rumble_sink: Callable[[int, int], None] | None = None,
    trigger_sink: Callable[[str, bytes], None] | None = None,
    lightbar_sink: Callable[[int, int, int], None] | None = None,
    player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None]
    | None = None,
    session_end_sink: Callable[[], None] | None = None,
    player: int = 1,
    allow_uhid: bool = True,
    calibration_0x05: bytes | None = None,
) -> VirtualPad | None:
    """Cria e **starta** o vpad do jogador `player`. None = nenhum backend subiu.

    Prefere o uhid quando tudo se alinha (máscara DualSense + /dev/uhid usável +
    permissão do chamador em `allow_uhid`); qualquer tropeço cai no
    `UinputGamepad`, que continua sendo o backend do Xbox 360 e o piso de
    compatibilidade. O blueprint é SEMPRE o canônico embutido
    (`uhid_blueprint.canonical_blueprint`) — o vpad não depende de controle
    físico conectado, nem de hidraw legível (VPAD-03/BT-01).

    REPLICA-03: os sinks de gatilho/lightbar/player-LED/fim-de-sessão replicam
    o output do JOGO ao controle físico — são exclusivos do backend uhid (o
    uinput é evdev-only: FF é o único output que chega até ele), então no
    fallback eles são deliberadamente descartados.

    `allow_uhid=False` (VPAD-08): o chamador declara "sem uhid" quando o backend
    do controle é o fake (`run.sh --fake`) — um vpad uhid é um DualSense Edge
    REAL no kernel, visível pela Steam, e o smoke não pode plantar um.

    GYRO-01: `calibration_0x05` é o feature 0x05 lido do controle FÍSICO deste
    jogador (`backend.read_calibration`) — quando presente e íntegro, o vpad o
    carimba no blueprint no lugar do canônico, para o motion espelhado ser
    calibrado com a unidade certa. None/inválido = canônico (fallback fail-safe;
    o vpad nasce do mesmo jeito). Exclusivo do backend uhid, como os sinks.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import (
        UinputGamepad,
        normalize_flavor,
    )

    key = normalize_flavor(flavor)
    motivo: str | None = None
    if allow_uhid:
        uhid, motivo = _try_uhid(
            key,
            rumble_sink=rumble_sink,
            trigger_sink=trigger_sink,
            lightbar_sink=lightbar_sink,
            player_led_sink=player_led_sink,
            session_end_sink=session_end_sink,
            player=player,
            calibration_0x05=calibration_0x05,
        )
        if uhid is not None:
            return uhid
    elif key == "dualsense":
        motivo = "uhid_vetado_pelo_chamador"
        logger.info("vpad_uhid_vetado_pelo_chamador_usando_uinput", player=player)
    pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)
    if motivo is not None:
        # VPAD-05 — fallback nunca silencioso: o PORQUÊ viaja com o vpad e o
        # `state_full` o expõe (`gamepad_emulation.degraded_motivo`) para a
        # GUI/doctor, sem ninguém precisar garimpar o journal.
        pad.fallback_motivo = motivo
    if not pad.start():
        return None
    return pad


def _try_uhid(
    flavor: str,
    *,
    rumble_sink: Callable[[int, int], None] | None,
    trigger_sink: Callable[[str, bytes], None] | None = None,
    lightbar_sink: Callable[[int, int, int], None] | None = None,
    player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None]
    | None = None,
    session_end_sink: Callable[[], None] | None = None,
    player: int,
    calibration_0x05: bytes | None = None,
) -> tuple[VirtualPad | None, str | None]:
    """Tenta o backend uhid; ``(None, motivo)`` = "use o uinput".

    O motivo vai ao log (como sempre foi) E volta ao chamador (VPAD-05): a
    factory o pendura no vpad uinput degradado para o `state_full` expor.
    ``(None, None)`` só no flavor xbox — uinput por design, não degradação.
    """
    from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UHID_NODE,
        UhidDualSense,
        uhid_available,
    )

    if flavor != "dualsense":
        # Xbox não é trabalho do uhid: o `hid_playstation` só faz bind em
        # VID/PID da Sony, e um device HID sem driver não vira gamepad nenhum.
        return None, None
    if not uhid_available():
        logger.info("vpad_uhid_indisponivel_usando_uinput", node=UHID_NODE, player=player)
        return None, "uhid_indisponivel"
    pad = UhidDualSense.for_flavor(
        flavor,
        rumble_sink=rumble_sink,
        trigger_sink=trigger_sink,
        lightbar_sink=lightbar_sink,
        player_led_sink=player_led_sink,
        session_end_sink=session_end_sink,
        player=player,
        blueprint=canonical_blueprint(),
        calibration_0x05=calibration_0x05,
    )
    if pad is None:  # pragma: no cover - o gate de flavor acima já garante
        return None, "uhid_indisponivel"
    if not pad.start():
        logger.warning("vpad_uhid_start_falhou_usando_uinput", player=player)
        return None, "uhid_start_falhou"
    if not pad.wait_for_bind(UHID_BIND_TIMEOUT_S):
        # O CREATE2 foi aceito mas o driver não fez bind (kernel sem
        # hid_playstation, MAC duplicado). Sem o `stop()` o device HID ficaria de
        # pé, mudo, disputando o jogo com o vpad uinput que vem a seguir.
        logger.warning("vpad_uhid_bind_falhou_usando_uinput", player=player)
        pad.stop()
        return None, "uhid_bind_falhou"
    logger.info("vpad_uhid_ativo", player=player, name=pad.name, mac=pad.mac)
    return pad, None


__all__ = ["UHID_BIND_TIMEOUT_S", "VirtualPad", "make_virtual_pad"]
