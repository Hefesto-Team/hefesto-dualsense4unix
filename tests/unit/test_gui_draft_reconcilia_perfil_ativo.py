"""R-08 (auditoria 23/07) — o draft da GUI reconcilia com o perfil ATIVO."""

from __future__ import annotations

from typing import Any

import pytest


def _draft_default() -> Any:
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    return DraftConfig.default()


class _AppFalsa:
    """Superfície mínima que `_reconciliar_draft_com_perfil_ativo` toca."""


    def _bootstrap_draft_async(self) -> None:
        self.bootstraps.append(self._draft_reload_for)

    def _status_toast(self, contexto: str, msg: str) -> None:
        self.toasts.append((contexto, msg))


def _sujar(app: _AppFalsa) -> None:
    """Simula edição de aba: as abas gravam SÓ em `self.draft`."""
    app.draft = app.draft.model_copy(
        update={"leds": app.draft.leds.model_copy(update={"lightbar_rgb": [9, 9, 9]})}
    )


class _Relogio:
    """Relógio injetável — o tempo destes testes é o do TESTE, não o da máquina."""

    def __init__(self, agora: float = 1000.0) -> None:
        self.agora = agora

    def monotonic(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


def test_perfil_igual_nao_dispara_nada() -> None:
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "FPS"})
    assert app.bootstraps == []
    assert app.toasts == []


def test_troca_de_perfil_sem_edicao_recarrega_o_draft() -> None:
    """O caso do autoswitch: ela abre o Sackboy e a GUI acompanha."""
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"], (
        "sem recarregar, as abas passam a editar e salvar o perfil ERRADO"
    )
    assert len(app.toasts) == 1, "a janela trocou o alvo do Salvar em silêncio"
    contexto, msg = app.toasts[0]
    assert contexto == "draft-reload"
    assert "sackboy_nativo" in msg and "Salvar" in msg


def test_edicao_pendente_avisa_em_vez_de_descartar() -> None:
    app = _AppFalsa(ativo="FPS")
    _sujar(app)
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == [], "recarregar por baixo da edição é perda de trabalho"
    assert len(app.toasts) == 1
    contexto, msg = app.toasts[0]
    assert contexto == "draft-reload"
    assert "sackboy_nativo" in msg and "FPS" in msg


@pytest.mark.parametrize("valor", [None, "", 123, {}])
def test_estado_sem_perfil_util_e_ignorado(valor: Any) -> None:
    app = _AppFalsa(ativo="FPS")
    app._reconciliar_draft_com_perfil_ativo({"active_profile": valor})
    assert app.bootstraps == []
    assert app.toasts == []


def test_sem_baseline_nao_ha_edicao_pendente() -> None:
    """Antes do primeiro carregamento não existe "sujo" — só desconhecido."""
    app = _AppFalsa(ativo="FPS")
    app._draft_baseline = None
    _sujar(app)
    assert app._tem_edicao_pendente() is False
    app._reconciliar_draft_com_perfil_ativo({"active_profile": "sackboy_nativo"})
    assert app.bootstraps == ["sackboy_nativo"]
