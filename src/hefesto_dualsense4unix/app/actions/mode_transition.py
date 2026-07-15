"""Transição de MODO do sistema — o único dono da sequência de IPC.

HARM-01 (SPRINT-HARMONIA-01, conceito 1 "um dono por conceito"): o modo tinha
DOIS donos com semântica divergente. A aba Início sempre saía do Modo Nativo
antes de ligar o gamepad; a aba Emulação chamava ``gamepad.emulation.set`` cru.
Pela Emulação, nativo e gamepad ficavam ligados JUNTOS — o controle físico
seguia grabado pelo jogo e o vpad nascia congelado: jogo sem controle nenhum,
com a Início ainda mostrando "Jogar direto (Sony)" (o nativo vence no
`_render_home`) e escondendo o estado real.

A cura não é repetir a sequência certa em cada aba — é não existir mais um
"segundo dono". Toda superfície da GUI que muda o modo passa por
:func:`apply_mode`; a ordem das chamadas e o timeout moram aqui.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.ipc_bridge import call_async

# HARM-08: um único default de máscara em TODAS as superfícies. Reexportado, não
# redefinido: um `DEFAULT_FLAVOR = "xbox"` aqui seria um segundo dono do valor —
# exatamente o defeito que este módulo existe para curar. O `uinput_gamepad` não
# puxa evdev no topo (só dentro das funções), então importá-lo aqui é barato.
from hefesto_dualsense4unix.integrations.uinput_gamepad import DEFAULT_FLAVOR

#: BUG-HOME-IPC-TIMEOUT-01: trocar de modo cria uinput + grab — bem mais que os
#: 0.25s default do `call_async`. Sem folga o toast dizia "Falha" com o modo JÁ
#: aplicado. Vale para QUALQUER caminho de troca de modo, não só o da Início.
MODE_IPC_TIMEOUT_S = 2.0

MODE_DESKTOP = "desktop"
MODE_GAMEPAD = "gamepad"
MODE_NATIVE = "native"

#: Os três modos, na ordem em que a Início os apresenta.
MODES: tuple[str, ...] = (MODE_DESKTOP, MODE_GAMEPAD, MODE_NATIVE)


def plan_mode_transition(
    mode_id: str, flavor: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Sequência de chamadas IPC que leva o sistema ao modo ``mode_id``.

    Função pura (sem GTK, sem daemon) — é a definição executável de "o que é
    cada modo". O worker do IPC consome as chamadas em ordem FIFO, então sair
    do nativo vem ANTES de ligar o gamepad: na ordem inversa o vpad nasceria
    com o físico ainda grabado pelo jogo.

    Levanta ``ValueError`` em modo desconhecido — um modo novo tem que passar
    por aqui em vez de virar um terceiro dono.
    """
    if mode_id == MODE_NATIVE:
        return [("native.mode.set", {"enabled": True})]
    if mode_id == MODE_GAMEPAD:
        return [
            ("native.mode.set", {"enabled": False}),
            (
                "gamepad.emulation.set",
                {"enabled": True, "flavor": flavor or DEFAULT_FLAVOR},
            ),
        ]
    if mode_id == MODE_DESKTOP:
        # FEAT-COOP-DEFAULT-ON-01: NÃO desliga o co-op — desligar o gamepad já
        # desmonta os jogadores; preservar a preferência faz o co-op voltar
        # sozinho ao reentrar em "Jogar pelo Hefesto".
        return [
            ("native.mode.set", {"enabled": False}),
            ("gamepad.emulation.set", {"enabled": False}),
        ]
    raise ValueError(f"modo desconhecido: {mode_id!r}")


def _ignore_ok(_result: Any) -> bool:
    return False


def _ignore_err(_exc: Exception) -> bool:
    return False


def apply_mode(
    mode_id: str,
    *,
    flavor: str | None = None,
    on_done: Callable[[Any], bool],
    on_fail: Callable[[Exception], bool],
) -> None:
    """Aplica ``mode_id`` disparando a sequência completa da transição.

    Só a ÚLTIMA chamada reporta para a UI: as intermediárias são preparo da
    transição e o resultado que interessa à usuária é o do passo final (ligar/
    desligar o gamepad). Todas levam ``MODE_IPC_TIMEOUT_S``.
    """
    steps = plan_mode_transition(mode_id, flavor)
    last = len(steps) - 1
    for idx, (method, params) in enumerate(steps):
        if idx == last:
            call_async(method, params, on_done, on_fail, timeout_s=MODE_IPC_TIMEOUT_S)
        else:
            call_async(
                method, params, _ignore_ok, _ignore_err, timeout_s=MODE_IPC_TIMEOUT_S
            )


def mode_of_state(state: dict[str, Any] | None) -> str | None:
    """Modo VIVO segundo o ``daemon.state_full``; ``None`` se offline.

    Ponto único de leitura: a Início e a Emulação derivavam o modo do mesmo
    payload com regras próprias e podiam discordar. O nativo vence o gamepad
    porque, quando os dois aparecem ligados, é o físico grabado que manda.
    """
    if not isinstance(state, dict):
        return None
    if state.get("native_mode"):
        return MODE_NATIVE
    gamepad = state.get("gamepad_emulation") or {}
    if isinstance(gamepad, dict) and gamepad.get("enabled"):
        return MODE_GAMEPAD
    return MODE_DESKTOP


__all__ = [
    "DEFAULT_FLAVOR",
    "MODES",
    "MODE_DESKTOP",
    "MODE_GAMEPAD",
    "MODE_IPC_TIMEOUT_S",
    "MODE_NATIVE",
    "apply_mode",
    "mode_of_state",
    "plan_mode_transition",
]
