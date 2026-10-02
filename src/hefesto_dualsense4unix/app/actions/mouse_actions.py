"""Aba Mouse: liga/desliga emulação de mouse+teclado via DualSense (FEAT-MOUSE-01)."""
# ruff: noqa: E402
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

logger = get_logger(__name__)


#: Mesmo vocabulário do bloco `keyboard_emulation` do daemon
#: (`ipc_handlers._keyboard_emulation_payload`), porque é a MESMA conjunção: a
#: **Alcançada desde 25/08/2026 (BG-02):** `mouse.emulation.set` devolve
BLOQUEIO_DO_MOUSE_EM_PORTUGUES: dict[str, str] = {
    "desligada": "a emulação de mouse está desligada no Hefesto",
    # o `disable_steam_input.sh` e o `fix_wireplumber_default_source.sh` — nem
    # `{gesto}` é trocado em `frase_da_recusa_do_mouse` pela frase única de
    "sem_device": "o mouse virtual não subiu — {gesto}",
    "modo_jogo": "o modo jogo está suspendendo mouse e teclado",
}

RECUSA_SEM_MOTIVO = (
    "O Hefesto recusou o pedido e não disse por quê. O mouse emulado não foi "
    "alterado."
)


def frase_da_recusa_do_mouse(resposta: object) -> str:
    """Texto do toast quando o Hefesto RESPONDE que não vai ligar/desligar.

    N6. `_on_ok` desviava toda resposta `status != "ok"` para o `_on_err` do
    timeout, cujo texto era *"Falha ao comunicar com o daemon"* — a janela
    acusando um defeito de comunicação que não houve. É a
    [ELO-MUDO-01](2026-08-22-ELO-MUDO-01-o-ok-que-nao-sabe-dizer-nao.md) ao
    contrário: em vez de comemorar o que não fez, culpar a rede.

    Pura de propósito — é o miolo do que ela lê, e precisa de teste sem montar
    janela (mesma disciplina de `descrever_teclado_emulado`).
    """
    bloqueio = resposta.get("bloqueio") if isinstance(resposta, dict) else None
    if not isinstance(bloqueio, str) or not bloqueio:
        return RECUSA_SEM_MOTIVO
    motivo = BLOQUEIO_DO_MOUSE_EM_PORTUGUES.get(bloqueio)
    if motivo is None:
        return (
            f"O Hefesto recusou o pedido (motivo: {bloqueio}). O mouse emulado "
            "não foi alterado."
        )
    motivo = motivo.replace("{gesto}", como_atualizar_esta_instalacao())
    return f"O Hefesto recusou: {motivo}. O mouse emulado não foi alterado."


__all__ = [
    "BLOQUEIO_DO_MOUSE_EM_PORTUGUES",
    "RECUSA_SEM_MOTIVO",
    "frase_da_recusa_do_mouse",
]

