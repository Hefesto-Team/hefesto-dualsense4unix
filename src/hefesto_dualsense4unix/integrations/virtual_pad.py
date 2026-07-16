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
O caminho uhid tem quatro pontos de falha (nó ausente/sem regra udev, controle
físico sem hidraw legível, CREATE2 recusado, `hid_playstation` que não faz bind) e
todos significam a mesma coisa para o chamador: **use o uinput**. Espalhar isso
pelos call sites daria uma versão diferente do fallback em cada um. Cada motivo é
logado (não silenciado): "caiu no uinput" sem dizer por quê é um bug que a usuária
sente no jogo e ninguém consegue diagnosticar.
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
    player: int = 1,
    hidraw_path: str | None = None,
) -> VirtualPad | None:
    """Cria e **starta** o vpad do jogador `player`. None = nenhum backend subiu.

    Prefere o uhid quando tudo se alinha (máscara DualSense + /dev/uhid usável +
    blueprint do controle físico em `hidraw_path`); qualquer tropeço cai no
    `UinputGamepad`, que continua sendo o backend do Xbox 360 e o piso de
    compatibilidade. `hidraw_path` é o nó do controle FÍSICO daquele jogador (o
    vpad copia dele o report descriptor e os features do probe).
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import (
        UinputGamepad,
        normalize_flavor,
    )

    key = normalize_flavor(flavor)
    uhid = _try_uhid(key, rumble_sink=rumble_sink, player=player, hidraw_path=hidraw_path)
    if uhid is not None:
        return uhid
    pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)
    if not pad.start():
        return None
    return pad


def _try_uhid(
    flavor: str,
    *,
    rumble_sink: Callable[[int, int], None] | None,
    player: int,
    hidraw_path: str | None,
) -> VirtualPad | None:
    """Tenta o backend uhid; None = "use o uinput" (com o motivo no log)."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UHID_NODE,
        UhidDualSense,
        capture_dualsense_blueprint,
        uhid_available,
    )

    if flavor != "dualsense":
        # Xbox não é trabalho do uhid: o `hid_playstation` só faz bind em
        # 054c:0ce6, e um device HID sem driver não vira gamepad nenhum.
        return None
    if hidraw_path is None:
        logger.info("vpad_uhid_sem_hidraw_usando_uinput", player=player)
        return None
    if not uhid_available():
        logger.info("vpad_uhid_indisponivel_usando_uinput", node=UHID_NODE, player=player)
        return None
    blueprint = capture_dualsense_blueprint(hidraw_path)
    if blueprint is None:
        logger.warning("vpad_uhid_blueprint_falhou_usando_uinput",
                       hidraw=hidraw_path, player=player)
        return None
    pad = UhidDualSense.for_flavor(
        flavor, rumble_sink=rumble_sink, player=player, blueprint=blueprint
    )
    if pad is None:  # pragma: no cover - o gate de flavor acima já garante
        return None
    if not pad.start():
        logger.warning("vpad_uhid_start_falhou_usando_uinput", player=player)
        return None
    if not pad.wait_for_bind(UHID_BIND_TIMEOUT_S):
        # O CREATE2 foi aceito mas o driver não fez bind (kernel sem
        # hid_playstation, MAC duplicado). Sem o `stop()` o device HID ficaria de
        # pé, mudo, disputando o jogo com o vpad uinput que vem a seguir.
        logger.warning("vpad_uhid_bind_falhou_usando_uinput", player=player)
        pad.stop()
        return None
    logger.info("vpad_uhid_ativo", player=player, name=pad.name, mac=pad.mac)
    return pad


__all__ = ["UHID_BIND_TIMEOUT_S", "VirtualPad", "make_virtual_pad"]
