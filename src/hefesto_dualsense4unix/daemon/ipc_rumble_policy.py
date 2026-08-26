"""Aplicação da política global de rumble sobre pares (weak, strong).

Extraído de `ipc_server.py` em AUDIT-FINDING-IPC-SERVER-SPLIT-01 para reduzir
acoplamento entre o dispatcher JSON-RPC e a lógica de multiplicador+debounce.

**O debounce do "auto" tem UMA memória, e é a do daemon** — `_last_auto_mult` e
`_last_auto_change_at`, declarados em `daemon/protocols.py`:82-84. As três rotas
de vibração leem e escrevem NELA: esta (o `rumble.set` da aba e o "Aplicar" do
rodapé), o tique de 200 ms do poll loop (`subsystems/rumble.reassert_rumble`) e
o force-feedback do jogo (`subsystems/gamepad._game_rumble_mult`).

**FATO ERRADO, SUBSTITUÍDO em 26/08/2026:** estas linhas diziam depender de
`RumbleEngine.update_auto_state` (AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01). O
`daemon._rumble_engine` **nunca é instanciado no daemon real** — a irmã desta
frase em `ipc_handlers.py` já registrava isso desde então. Consequência medida:
a leitura caía sempre em 0,7/0,0 e o writeback era jogado fora pelo
`if rumble_engine is not None`, então esta rota tinha uma SEGUNDA conta do mesmo
número. A intensidade que ela sente pulava conforme qual rota mexeu por último.
"""
from __future__ import annotations

import time as _time
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def memoria_viva_do_auto(daemon: Any) -> tuple[float, float]:
    """O estado de debounce do "auto" que vale AGORA: (mult, instante).

    Lê os DOIS campos do daemon — a mesma dupla que `reassert_rumble` e
    `_game_rumble_mult` leem — e devolve os defaults do primeiro tique
    (0,7 / 0,0) quando eles ainda não existem.

    A blindagem por `isinstance` não é zelo: o daemon aqui é `Any`, e boa parte
    dos dublês desta casa é `MagicMock`, que devolve um `Mock` para QUALQUER
    atributo. Sem ela, `now - last_auto_change_at` estouraria `TypeError` dentro
    de `_effective_mult` e a vibração morreria no dublê em vez de no produto.
    `bool` é recusado à parte porque `isinstance(True, int)` é verdadeiro.
    """
    mult = getattr(daemon, "_last_auto_mult", None)
    quando = getattr(daemon, "_last_auto_change_at", None)
    if isinstance(mult, bool) or not isinstance(mult, (int, float)):
        mult = 0.7
    if isinstance(quando, bool) or not isinstance(quando, (int, float)):
        quando = 0.0
    return float(mult), float(quando)


def apply_rumble_policy(daemon: Any, weak: int, strong: int) -> tuple[int, int]:
    """Aplica multiplicador de política de rumble sobre (weak, strong).

    Consulta a config do daemon e a memória viva do debounce do "auto"
    (`memoria_viva_do_auto`, acima). Se daemon ausente ou sem config, retorna
    os valores sem alteração.
    """
    daemon_cfg = getattr(daemon, "config", None) if daemon else None
    if daemon_cfg is None:
        return weak, strong

    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.lifecycle import AUTO_DEBOUNCE_SEC

    # Bateria do estado mais recente (via store se disponível).
    battery_pct = 50
    store = getattr(daemon, "store", None)
    if store is not None:
        try:
            snap = store.snapshot()
            ctrl = snap.controller
            if ctrl is not None and ctrl.battery_pct is not None:
                battery_pct = int(ctrl.battery_pct)
        except Exception:
            logger.debug("rumble_policy_state_read_fallback", exc_info=True)

    # Debounce auto: a memória VIVA do daemon (ver o docstring do módulo).
    last_auto_mult, last_auto_change_at = memoria_viva_do_auto(daemon)

    mult, new_last_auto_mult, new_last_auto_change_at = _effective_mult(
        config=daemon_cfg,
        battery_pct=battery_pct,
        now=_time.monotonic(),
        last_auto_mult=last_auto_mult,
        last_auto_change_at=last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )

    # Writeback na MESMA dupla que as outras duas rotas escrevem, e pelo mesmo
    # idioma que `reassert_rumble` já usava — atribuição direta. `_last_auto_mult`
    # é também a fonte da observabilidade: é dele que `state_full` tira o
    # `rumble_mult_applied`. Sem este writeback, o valor publicado na tela
    # continuaria descrevendo a ÚLTIMA rota que escreveu, não a que acabou de
    # rodar.
    daemon._last_auto_mult = new_last_auto_mult
    daemon._last_auto_change_at = new_last_auto_change_at

    eff_weak = max(0, min(255, round(weak * mult)))
    eff_strong = max(0, min(255, round(strong * mult)))
    return eff_weak, eff_strong


def uniq_do_alvo_de_output(controller: Any) -> str | None:
    """MAC do alvo de output NESTE instante, ou None para "a mesa inteira".

    MESA-CHEIA-05 (E0). Quem fixa um valor TRANSITÓRIO (rumble) precisa
    congelar o endereço no gesto: o alvo do backend é um ponteiro mutável
    (`_output_target_key`), e o `reassert_rumble` do poll loop reescrevia no
    alvo DE AGORA — trocar o seletor levava o valor fixado no Controle 2 para
    o Controle 3, 200 ms depois.

    **Um dono só para os dois gestos que fixam rumble**: a aba Rumble
    (`rumble.set`/`rumble.stop`) e o "Aplicar" do rodapé (`DraftApplier`).
    Eram duas cópias da mesma leitura, e duas cópias divergem na primeira
    mudança.

    Backends sem o método (FakeController, single-instance) devolvem None e
    seguem no broadcast histórico. None também quando o alvo é "Todos" ou não
    tem MAC 12-hex — sem endereço estável não há o que guardar.
    """
    getter = getattr(controller, "get_output_target_uniq", None)
    if not callable(getter):
        return None
    try:
        alvo = getter()
    except Exception:
        logger.debug("output_target_uniq_indisponivel", exc_info=True)
        return None
    return alvo if isinstance(alvo, str) and alvo else None


# Alias mantido por compat interna — chamadas legadas via `_apply_rumble_policy`
# continuam resolvendo. Código novo deve usar `apply_rumble_policy` (sem prefixo
# underscore) visto que a função é exportada a partir deste módulo.
_apply_rumble_policy = apply_rumble_policy


__all__ = [
    "_apply_rumble_policy",
    "apply_rumble_policy",
    "memoria_viva_do_auto",
    "uniq_do_alvo_de_output",
]
