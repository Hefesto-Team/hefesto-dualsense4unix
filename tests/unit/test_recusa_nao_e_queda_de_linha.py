"""RECUSA-NAO-E-QUEDA-DE-LINHA-01 — a aba Navegação para de culpar a rede."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("recusa não é queda de linha")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    RECUSA_SEM_MOTIVO,
    frase_da_recusa_do_mouse,
)


class _FakeSwitch:
    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._active = False
        self.sensitive = True

    def get_active(self) -> bool:
        return self._active


    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)


def _responder(monkeypatch: pytest.MonkeyPatch, resposta: Any) -> list[str]:
    """Faz o IPC responder `resposta` sincronamente. Devolve os métodos vistos."""
    metodos: list[str] = []

    def fake_call_async(
        method: str,
        params: dict[str, Any] | None,
        on_success: Any,
        on_failure: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        metodos.append(method)
        on_success(resposta)

    monkeypatch.setattr(ipc_bridge, "call_async", fake_call_async)
    return metodos


def test_a_recusa_com_motivo_conhecido_vira_frase_de_gente() -> None:
    frase = frase_da_recusa_do_mouse({"status": "failed", "bloqueio": "modo_jogo"})
    assert BLOQUEIO_DO_MOUSE_EM_PORTUGUES["modo_jogo"] in frase
    assert "não foi alterado" in frase
    assert "comunicar" not in frase and "Falha" not in frase, (
        "a recusa continua acusando um defeito de comunicação que não houve"
    )


def test_a_recusa_sem_motivo_diz_que_o_motivo_faltou() -> None:
    """Enquanto a N5 não publicar `bloqueio`, é ESTE o caminho de produção."""
    assert frase_da_recusa_do_mouse({"status": "failed"}) == RECUSA_SEM_MOTIVO
    assert "não disse por quê" in RECUSA_SEM_MOTIVO


def test_motivo_novo_de_um_daemon_mais_novo_sai_cru_e_honesto() -> None:
    frase = frase_da_recusa_do_mouse({"status": "failed", "bloqueio": "asa_nova"})
    assert "asa_nova" in frase, (
        "motivo desconhecido virou silêncio — dizer o código cru é feio, e é "
        "melhor que afirmar que funcionou"
    )


@pytest.mark.parametrize("resposta", [None, {}, {"bloqueio": 7}, "texto"])
def test_resposta_torta_nao_derruba_a_traducao(resposta: Any) -> None:
    assert frase_da_recusa_do_mouse(resposta) == RECUSA_SEM_MOTIVO


