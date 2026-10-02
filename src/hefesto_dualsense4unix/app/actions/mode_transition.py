"""Transição de MODO do sistema — o único dono da sequência de IPC."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.ipc_bridge import call_async
from hefesto_dualsense4unix.integrations.uinput_gamepad import DEFAULT_FLAVOR

MODE_IPC_TIMEOUT_S = 2.0

#: HARM-15: folga para LER o modo (`daemon.state_full`). O daemon monta o estado
#: da usuária. Mora junto de `mode_of_state` porque é a MESMA leitura.
STATE_IPC_TIMEOUT_S = 1.0

MODE_DESKTOP = "desktop"
MODE_GAMEPAD = "gamepad"
MODE_NATIVE = "native"

MODES: tuple[str, ...] = (MODE_DESKTOP, MODE_GAMEPAD, MODE_NATIVE)


def plan_mode_transition(
    mode_id: str, flavor: str | None = None, caminho: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Sequência de chamadas IPC que leva o sistema ao modo ``mode_id``.

    Função pura (sem GTK, sem daemon) — é a definição executável de "o que é
    cada modo". O worker do IPC consome as chamadas em ordem FIFO, então sair
    do nativo vem ANTES de ligar o gamepad: na ordem inversa o vpad nasceria
    com o físico ainda grabado pelo jogo.

    O daemon TAMBÉM garante essa saída (`set_gamepad_emulation` — HARM-01), por
    causa das superfícies que não podem importar este módulo (a CLI arrastaria
    GTK junto). O passo daqui não virou redundância descartável de propósito:
    sem ele o plano deixaria de dizer o que o modo gamepad é, e a GUI passaria a
    depender em silêncio da versão do daemon do outro lado do socket (um .deb
    antigo traria o defeito de volta). Custa uma chamada idempotente.

    AUTO-01.3 — **um dono só para a máscara, e ele é o daemon.** Sem `flavor`
    explícito o passo sai SEM o campo, e o daemon preserva a máscara que já
    está configurada (contrato do `ipc_handlers._handle_gamepad_emulation_set`:
    "flavor é opcional; mantém o atual se ausente"). Antes injetávamos
    ``DEFAULT_FLAVOR`` aqui, e isso fazia o MESMO gesto entregar máscaras
    DIFERENTES conforme a porta de entrada: `gamepad on` pela linha de comando
    preservava a máscara do daemon (`dualsense` numa instalação nova, por
    HARMONIA-MASK-01) enquanto "Jogar pelo Hefesto" impunha `xbox`. E a máscara
    decide se o jogo reconhece o controle — o `DEFAULT_FLAVOR` da GUI era um
    segundo dono do valor, dentro do módulo criado para acabar com eles. A CLI
    já fazia certo desde o HARM-08 (`test_cli_gamepad`); agora as duas portas
    dizem a mesma coisa. Escolha explícita dela (o seletor de máscara) continua
    indo no campo, intacta.

    Levanta ``ValueError`` em modo desconhecido — um modo novo tem que passar
    por aqui em vez de virar um terceiro dono.

    ORIGEM-QUE-MENTE-01 (08/08/2026): todo passo que define modo viaja com
    ``origin="manual"``. É AQUI que o clique dela vira pedido, e o daemon
    precisa saber disso: desde a cura da origem, o silêncio no protocolo
    significa "automático", e automático NÃO fura o portão da allowlist do
    Steam Input.

    MEDIDO na máquina dela, e o custo foi imediato: com o Sackboy marcado, o
    botão "Jogar pelo Hefesto" parou de funcionar — o clique chegava sem
    ``origin``, era lido como reconciliação e o daemon o recusava com
    ``gamepad_start_recusado_steam_input``. A cura tinha um contrapeso escrito
    no teste (*"quem declara manual continua sendo tratado como gesto dela"*) e
    faltava esta metade: **a janela precisa DECLARAR**.

    O ``mouse.emulation.restore`` não leva ``origin``: ele restaura a
    preferência persistida, que é reconciliação por definição.

    O PASSO GAMEPAD CARREGA O CAMINHO — MODO-DE-CONEXAO-01, 13/09/2026. O chip
    de modo da aba Jogar mandava ``flavor``, que no daemon é só o padrão da
    MÁSCARA: com máscara escolhida no cartão ele respondia «aplicado» e o jogo
    seguia recebendo o mesmo aparelho. O modo é o ``caminho`` (``"dualsense"`` ·
    ``"xbox"``), e ele vai no seu próprio campo. ``flavor`` continua existindo
    para quem escolhe MÁSCARA por aqui; os dois não se confundem mais.
    """
    if mode_id == MODE_NATIVE:
        return [("native.mode.set", {"enabled": True, "origin": "manual"})]
    if mode_id == MODE_GAMEPAD:
        ligar: dict[str, Any] = {"enabled": True, "origin": "manual"}
        if flavor:
            ligar["flavor"] = flavor
        if caminho:
            ligar["caminho"] = caminho
        return [
            ("native.mode.set", {"enabled": False, "origin": "manual"}),
            ("gamepad.emulation.set", ligar),
        ]
    if mode_id == MODE_DESKTOP:
        # a ORDEM não mudou. Era `mouse.emulation.restore`, que lê a flag de
        # `key_bindings`, `button_actions` e a supressão. A ordem dela: *"o modo
        return [
            ("native.mode.set", {"enabled": False, "origin": "manual"}),
            ("gamepad.emulation.set", {"enabled": False, "origin": "manual"}),
            ("desktop.arranjo.apply", {"origin": "manual"}),
        ]
    raise ValueError(f"modo desconhecido: {mode_id!r}")


def _ignore_ok(_result: Any) -> bool:
    return False


def _ignore_err(_exc: Exception) -> bool:
    return False


_MODE_DEFINING_METHODS = frozenset({"native.mode.set", "gamepad.emulation.set"})


def reported_step_index(steps: list[tuple[str, dict[str, Any]]]) -> int:
    """Índice do passo cujo resultado a usuária vê (função pura)."""
    for idx in range(len(steps) - 1, -1, -1):
        if steps[idx][0] in _MODE_DEFINING_METHODS:
            return idx
    return len(steps) - 1


def apply_mode(
    mode_id: str,
    *,
    flavor: str | None = None,
    caminho: str | None = None,
    on_done: Callable[[Any], bool],
    on_fail: Callable[[Exception], bool],
) -> None:
    """Aplica ``mode_id`` disparando a sequência completa da transição."""
    steps = plan_mode_transition(mode_id, flavor, caminho)
    reported = reported_step_index(steps)
    for idx, (method, params) in enumerate(steps):
        if idx == reported:
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
    "STATE_IPC_TIMEOUT_S",
    "apply_mode",
    "mode_of_state",
    "plan_mode_transition",
    "reported_step_index",
]
