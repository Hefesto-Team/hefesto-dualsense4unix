"""RECUSA-NAO-E-QUEDA-DE-LINHA-01 — a aba Navegação para de culpar a rede.

Dois defeitos da mesma aba, medidos em 23/08/2026 (sprint NAVEGAÇÃO — UM
CONTROLE SÓ-01, §2.2), e os dois são a tela afirmando o que não sabe:

N4 — o interruptor do mouse com `mode is None` (Hefesto sem resposta) ficava
     APAGADO e MUDO: `texto = MODE_GATE_HINT if blocked and mode is not None
     else ""`. É o que a foto oficial das 18h15 mostra. Um interruptor cinza sem
     uma palavra ao lado é lido como defeito do produto, não como ausência de
     resposta — e a frase do modo jogo não serve aqui, porque ela AFIRMA que há
     jogo em andamento.

N6 — quando o Hefesto RECUSA (`status != "ok"`), `_on_ok` desviava para o
     `_on_err` do timeout, cujo texto era *"Falha ao comunicar com o daemon"*.
     É a ELO-MUDO-01 ao contrário: em vez de comemorar o que não fez, acusar um
     defeito de comunicação que não houve.

O teste do gate de N4 mora em `test_harmonia_mouse_um_dono.py`, junto com os
irmãos dele (o arquivo é o dono daquele gate). Aqui ficam a função pura da
recusa e o caminho vivo do interruptor.

Estes testes MORDEM: devolver o desvio para o `_on_err` faz o primeiro bloco
reprovar; apagar a tabela de motivos faz o segundo reprovar.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi` (mesma disciplina dos
# irmãos desta aba — o stub que outro arquivo planta passaria pelo importorskip).
exigir_gi_real("recusa não é queda de linha")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    RECUSA_SEM_MOTIVO,
    SEM_RESPOSTA_DO_HEFESTO,
    MouseActionsMixin,
    frase_da_recusa_do_mouse,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig


class _FakeSwitch:
    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self._active = False
        self.sensitive = True

    def get_active(self) -> bool:
        return self._active

    def set_active(self, value: bool) -> None:
        self._active = bool(value)
        self._owner.on_mouse_toggle_set(self, bool(value))

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)


class _Harness(MouseActionsMixin):
    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.widgets: dict[str, Any] = {}
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return self.widgets.get(widget_id)

    def _toast_mouse(self, msg: str) -> None:
        self.toasts.append(msg)


def _harness() -> tuple[_Harness, _FakeSwitch]:
    harness = _Harness()
    switch = _FakeSwitch(harness)
    harness.widgets["mouse_emulation_toggle"] = switch
    return harness, switch


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


# --- a função pura ------------------------------------------------------


def test_a_recusa_com_motivo_conhecido_vira_frase_de_gente() -> None:
    frase = frase_da_recusa_do_mouse({"status": "failed", "bloqueio": "modo_jogo"})
    assert BLOQUEIO_DO_MOUSE_EM_PORTUGUES["modo_jogo"] in frase
    assert "não foi alterado" in frase
    assert "comunicar" not in frase and "Falha" not in frase, (
        "a recusa continua acusando um defeito de comunicação que não houve"
    )


def test_a_recusa_sem_motivo_diz_que_o_motivo_faltou() -> None:
    """Enquanto a N5 não publicar `bloqueio`, é ESTE o caminho de produção.

    A frase não pode inventar um motivo nem culpar a rede: as duas coisas
    afirmam o que não se sabe.
    """
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


def test_a_recusa_e_a_falta_de_resposta_sao_TEXTOS_DIFERENTES() -> None:  # noqa: N802  # noqa-acento: nome de teste em maiúsculas para destacar o ponto
    """O defeito era um texto só para as duas coisas."""
    assert RECUSA_SEM_MOTIVO != SEM_RESPOSTA_DO_HEFESTO
    for motivo in BLOQUEIO_DO_MOUSE_EM_PORTUGUES.values():
        assert motivo not in SEM_RESPOSTA_DO_HEFESTO


# --- o caminho vivo do interruptor --------------------------------------


def test_daemon_que_recusa_com_motivo_produz_o_toast_do_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, switch = _harness()
    _responder(monkeypatch, {"status": "failed", "bloqueio": "modo_jogo"})

    switch.set_active(True)

    assert harness.toasts == [
        frase_da_recusa_do_mouse({"status": "failed", "bloqueio": "modo_jogo"})
    ]
    assert harness.toasts[0] != SEM_RESPOSTA_DO_HEFESTO, (
        "a recusa do Hefesto ainda cai no texto de queda de linha"
    )
    assert switch.get_active() is False, (
        "a reversão do interruptor é a mesma nas duas saídas de insucesso "
        "(BUG-MOUSE-TOGGLE-STALE-REVERT-01) — N6 separou os TEXTOS"
    )
    assert harness.draft.mouse.enabled is False, "nada foi aplicado no rascunho"


def test_daemon_que_aceita_continua_comemorando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua do lado bom: separar as saídas não pode quebrar o sucesso."""
    harness, switch = _harness()
    _responder(monkeypatch, {"status": "ok", "enabled": True})

    switch.set_active(True)

    assert harness.toasts == ["Mouse emulado ligado"]
    assert switch.get_active() is True
    assert harness.draft.mouse.enabled is True
