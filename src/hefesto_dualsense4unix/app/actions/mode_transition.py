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
#
# AUTO-01.3: este valor deixou de ser INJETADO no plano — ver
# `plan_mode_transition`. Ele segue sendo o piso de compatibilidade do projeto
# (o default dos presets e o fallback do `normalize_flavor`) e continua
# reexportado aqui para quem precisa exibi-lo; o que não pode voltar a existir é
# a GUI escolher uma máscara por conta própria quando ninguém escolheu.
from hefesto_dualsense4unix.integrations.uinput_gamepad import DEFAULT_FLAVOR

#: BUG-HOME-IPC-TIMEOUT-01: trocar de modo cria uinput + grab — bem mais que os
#: 0.25s default do `call_async`. Sem folga o toast dizia "Falha" com o modo JÁ
#: aplicado. Vale para QUALQUER caminho de troca de modo, não só o da Início.
MODE_IPC_TIMEOUT_S = 2.0

#: HARM-15: folga para LER o modo (`daemon.state_full`). O daemon monta o estado
#: varrendo os controles e sob carga (hotplug, co-op subindo) passa dos 0.25s
#: default — sem folga a UI declarava o daemon morto/desconhecido com ele VIVO.
#: Menor que a da troca de modo: aqui o custo de esperar é um tick, não uma ação
#: da usuária. Mora junto de `mode_of_state` porque é a MESMA leitura.
STATE_IPC_TIMEOUT_S = 1.0

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
    """
    if mode_id == MODE_NATIVE:
        return [("native.mode.set", {"enabled": True})]
    if mode_id == MODE_GAMEPAD:
        ligar: dict[str, Any] = {"enabled": True}
        if flavor:
            ligar["flavor"] = flavor
        return [
            ("native.mode.set", {"enabled": False}),
            ("gamepad.emulation.set", ligar),
        ]
    if mode_id == MODE_DESKTOP:
        # FEAT-COOP-DEFAULT-ON-01: NÃO desliga o co-op — desligar o gamepad já
        # desmonta os jogadores; preservar a preferência faz o co-op voltar
        # sozinho ao reentrar em "Jogar pelo Hefesto".
        # HARM-06: o modo desktop é o DONO da emulação de mouse/teclado, então
        # entrar nele LIGA o mouse (conforme a preferência que o daemon
        # persistiu) em vez de só desligar os outros dois modos e deixar o
        # controle sem função nenhuma até alguém achar a aba Mouse. Vem por
        # último: ligar o mouse antes de o gamepad sair faria a exclusão mútua
        # do daemon derrubar o mouse recém-ligado.
        return [
            ("native.mode.set", {"enabled": False}),
            ("gamepad.emulation.set", {"enabled": False}),
            ("mouse.emulation.restore", {}),
        ]
    raise ValueError(f"modo desconhecido: {mode_id!r}")


def _ignore_ok(_result: Any) -> bool:
    return False


def _ignore_err(_exc: Exception) -> bool:
    return False


#: Métodos que DEFINEM o modo — os outros passos do plano são consequência dele.
#: Quem reporta à UI é o último passo definidor: falhar em restaurar o mouse
#: (HARM-06) não é falhar em entrar no modo desktop, e um toast "Falha ao mudar
#: o modo" com o modo JÁ aplicado é a UI mentindo (o defeito que este sprint cura).
_MODE_DEFINING_METHODS = frozenset({"native.mode.set", "gamepad.emulation.set"})


def reported_step_index(steps: list[tuple[str, dict[str, Any]]]) -> int:
    """Índice do passo cujo resultado a usuária vê (função pura).

    É o último passo DEFINIDOR do modo; sem nenhum (plano só de consequências,
    que hoje não existe) reporta o último, para nunca ficar sem feedback.
    """
    for idx in range(len(steps) - 1, -1, -1):
        if steps[idx][0] in _MODE_DEFINING_METHODS:
            return idx
    return len(steps) - 1


def apply_mode(
    mode_id: str,
    *,
    flavor: str | None = None,
    on_done: Callable[[Any], bool],
    on_fail: Callable[[Exception], bool],
) -> None:
    """Aplica ``mode_id`` disparando a sequência completa da transição.

    Só UMA chamada reporta para a UI — a que define o modo (ver
    `reported_step_index`); as demais são preparo ou consequência. Todas levam
    ``MODE_IPC_TIMEOUT_S``.
    """
    steps = plan_mode_transition(mode_id, flavor)
    reported = reported_step_index(steps)
    for idx, (method, params) in enumerate(steps):
        if idx == reported:
            call_async(method, params, on_done, on_fail, timeout_s=MODE_IPC_TIMEOUT_S)
        else:
            call_async(
                method, params, _ignore_ok, _ignore_err, timeout_s=MODE_IPC_TIMEOUT_S
            )


#: AUTO-01.2: o passo do plano de co-op cujo resultado a usuária vê. É o
#: `coop.set`: entrar no modo jogo é PREPARO (e já tem toast próprio quando ela
#: usa o comutador) e a renumeração é ACABAMENTO — nenhum dos dois responde a
#: pergunta "vai dar co-op?". Mesmo desenho do `reported_step_index`.
COOP_PREP_REPORTED_METHOD = "coop.set"


def plan_coop_prep(flavor: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Sequência IPC de "Preparar co-op" — função pura (AUTO-01.2).

    O co-op local é a funcionalidade central do projeto (quatro jogadores) e
    ``grep -ci coop gui/main.glade`` devolvia **zero**: ele só existia por linha
    de comando (`hefesto-dualsense4unix coop on`). O próprio código já admitia o
    buraco — a migração do `utils/session.migrate_coop_optout` existe porque,
    sem ela, o co-op ficaria desligado *"sem nenhum caminho de volta na
    interface"*.

    Nada aqui é implementação nova: todo o IPC já existia. O que faltava era a
    LIGAÇÃO — um clique em vez de dez. Os três passos, em ordem FIFO:

    1. o modo jogo (`plan_mode_transition`) — sem gamepad virtual de pé o gate
       do co-op (`CoopManager.should_be_active`) nunca abre, e é ele que faz o
       P1 existir para os P2+ nascerem ao lado;
    2. ``coop.set`` — cada controle físico vira um jogador com vpad próprio, em
       vez de todos alimentarem o mesmo;
    3. ``identity.renumber`` — compacta a numeração para 1..N. É o acabamento
       que faz os LEDs de jogador baterem com o que o jogo vê ("sony 1 / sony
       4" com dois controles na mesa era a queixa). O daemon RECUSA renumerar
       com jogo aberto (`sessao_de_jogo_aberta`), e por isso este passo vem por
       último: uma recusa aqui não desfaz nada do que os dois primeiros já
       entregaram.

    ``flavor`` segue a regra do AUTO-01.3: só vai no IPC quando ela escolheu
    uma máscara; ausente, quem decide é o daemon.
    """
    return [
        *plan_mode_transition(MODE_GAMEPAD, flavor),
        ("coop.set", {"enabled": True}),
        ("identity.renumber", {}),
    ]


def apply_coop_prep(
    *,
    flavor: str | None = None,
    on_done: Callable[[Any], bool],
    on_fail: Callable[[Exception], bool],
) -> None:
    """Dispara a sequência de "Preparar co-op" (AUTO-01.2).

    Só o passo `COOP_PREP_REPORTED_METHOD` reporta para a UI; os demais são
    preparo/acabamento e falham em silêncio (a renumeração recusada com jogo
    aberto não pode virar "falhou ao preparar o co-op" com o co-op JÁ de pé —
    seria a UI mentindo, o mesmo defeito que o `reported_step_index` cura na
    troca de modo). Todos levam ``MODE_IPC_TIMEOUT_S``: cada um cria ou
    desmonta uinput/grab.
    """
    for method, params in plan_coop_prep(flavor):
        if method == COOP_PREP_REPORTED_METHOD:
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
    "COOP_PREP_REPORTED_METHOD",
    "DEFAULT_FLAVOR",
    "MODES",
    "MODE_DESKTOP",
    "MODE_GAMEPAD",
    "MODE_IPC_TIMEOUT_S",
    "MODE_NATIVE",
    "STATE_IPC_TIMEOUT_S",
    "apply_coop_prep",
    "apply_mode",
    "mode_of_state",
    "plan_coop_prep",
    "plan_mode_transition",
    "reported_step_index",
]
