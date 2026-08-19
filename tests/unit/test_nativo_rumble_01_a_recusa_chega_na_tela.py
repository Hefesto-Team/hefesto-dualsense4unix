"""NATIVO-RUMBLE-01, a metade da GUI: a recusa do daemon chega aos olhos dela.

O daemon já recusa `rumble.set` no Modo Nativo, com motivo — mas a recusa vem
no **corpo** de uma resposta bem-sucedida (`status: "recusado"`), não como erro
JSON-RPC. O `_call_checked` da aba Gatilhos lê `CODE_INVALID_PARAMS` e devolve
`(True, None)` para esta forma: para ele, o RPC deu certo.

Sem esta leitura, a aba Rumble diria "Vibração travada (fraca=…, forte=…)" com
o motor parado — que é exatamente a mentira que a medição de 19/08/2026
encontrou, e a mesma classe de defeito do HARM-19 pelo avesso: lá a UI acusava
o daemon de morto quando ele estava vivo e recusando; aqui ela comemora quando
ele recusou.

**Como estes testes MORDEM:** arranque o `_recusa_no_corpo` (ou faça
`rumble_set_checked` chamar `rumble_set`) e os quatro reprovam — o toast volta a
dizer "travada", e o teste do temporizador mostra que um `Parar` seria agendado
sobre um pedido que nunca chegou ao aparelho.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
    RUMBLE_RECUSADO_MODO_NATIVO,
)

# A resposta LITERAL que `_handle_rumble_set` devolve sob Modo Nativo. Copiada
# do handler de propósito: se a forma mudar lá e não aqui, é este arquivo que
# grita — que é o serviço que um dublê presta.
RESPOSTA_DE_RECUSA: dict[str, Any] = {
    "status": "recusado",
    "desfecho": RUMBLE_RECUSADO_MODO_NATIVO,
    "motivo": MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
    "weak": 0,
    "strong": 0,
    "passthrough": True,
}

RESPOSTA_DE_ACEITE: dict[str, Any] = {
    "status": "ok",
    "desfecho": "aplicado",
    "weak": 160,
    "strong": 220,
}


class TestRumbleSetChecked:
    """A ponte de IPC distingue "recusou" de "aplicou" e de "não respondeu"."""

    def test_recusa_no_corpo_vira_motivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, RESPOSTA_DE_RECUSA)
        )
        ok, motivo = ipc_bridge.rumble_set_checked(160, 220)
        assert ok is False, "recusa do daemon não pode voltar como sucesso"
        assert motivo == MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES

    def test_aceite_nao_inventa_motivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, RESPOSTA_DE_ACEITE)
        )
        assert ipc_bridge.rumble_set_checked(160, 220) == (True, None)

    def test_daemon_mudo_continua_sem_motivo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transporte caído é (False, None) — a UI aí SIM fala do daemon."""
        monkeypatch.setattr(ipc_bridge, "_safe_call", lambda *a, **k: (False, None))
        assert ipc_bridge.rumble_set_checked(160, 220) == (False, None)

    def test_daemon_velho_sem_o_campo_status_nao_quebra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O daemon vivo é mais velho que o código: resposta sem `status` vale.

        Instalação editable — a GUI nova conversa com o daemon que subiu antes
        dela até o próximo start. Uma resposta antiga (`{"weak":…, "strong":…}`)
        não pode virar recusa fantasma.
        """
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, {"weak": 160, "strong": 220})
        )
        assert ipc_bridge.rumble_set_checked(160, 220) == (True, None)
