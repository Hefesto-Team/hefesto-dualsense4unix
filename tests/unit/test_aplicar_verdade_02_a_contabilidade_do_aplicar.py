"""APLICAR-VERDADE-02 (28/07) — a contabilidade do "Aplicar" para de mentir.

O e8f9060 curou a FRASE do rodapé: ela não diz mais "Perfil aplicado ao
controle." quando nada foi aplicado. Ficou de pé, declarado no próprio commit,
o resto da mentira em `footer_actions.on_apply_draft`: `ok` era
`result.get("status") == "ok"`, e esse `status` é fixo em `"ok"` por contrato
do `profile.apply_draft` (é "recebi", não "apliquei"). Consequências medidas
aqui:

  - `_clear_mouse_dirty()` baixava a pendência da aba Mouse com as sete seções
    FORA — a edição sumia sem nunca ter chegado ao controle;
  - `logger.info(..., ok=True)` carimbava sucesso no journal do mesmo evento.

Agora são duas perguntas separadas: `aceita` (o daemon respondeu — decide a
FRASE) e `aplicou` (alguma seção entrou — decide o `dirty` e o journal). E a
pendência do mouse só acaba se a seção MOUSE entrou, não se "algo" entrou.

Compatibilidade preservada de propósito: resposta SEM `applied` (daemon antigo,
ou o `True` cru do bridge) continua contando como aplicada — mesma regra que
`_mensagem_de_aplicacao` já usava para o texto. As duas não podem divergir.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi` (ver o irmão
# test_harmonia_mouse_um_dono.py).
exigir_gi_real("aplicar verdade 02")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig


class _FooterStub(FooterActionsMixin):
    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return None

    def _status_toast(self, _context: str, msg: str) -> None:
        self.toasts.append(msg)


@pytest.fixture()
def resposta(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`profile.apply_draft` síncrono, com a resposta controlada pelo teste."""
    caixa: dict[str, Any] = {"result": {"status": "ok"}}

    def _fake(
        _method: str,
        _params: Any,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        on_success(caixa["result"])

    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _fake)
    return caixa


@pytest.fixture()
def journal(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura o que o rodapé carimba no journal."""
    linhas: list[dict[str, Any]] = []
    monkeypatch.setattr(
        footer_actions.logger,
        "info",
        lambda evento, **campos: linhas.append({"evento": evento, **campos}),
    )
    return linhas


def _com_mouse_pendente(stub: _FooterStub) -> None:
    stub.draft = stub.draft.model_copy(
        update={
            "mouse": stub.draft.mouse.model_copy(
                update={"enabled": True, "dirty": True}
            )
        }
    )


# ---------------------------------------------------------------------------
# As sete seções fora
# ---------------------------------------------------------------------------


def test_nada_aplicado_nao_baixa_o_dirty_do_mouse(
    resposta: dict[str, Any], journal: list[dict[str, Any]]
) -> None:
    """O defeito declarado no e8f9060: com `applied=[]` o rodapé já dizia a
    verdade, mas a pendência do mouse era baixada assim mesmo."""
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = {
        "status": "ok",
        "applied": [],
        "failed": {"mouse": "uinput fechado", "leds": "sem controle"},
    }

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is True
    assert journal[-1]["ok"] is False
    assert journal[-1]["aceita"] is True


def test_nada_aplicado_ainda_diz_a_frase_certa(resposta: dict[str, Any]) -> None:
    """A cura do e8f9060 continua de pé: `aplicou=False` não pode virar
    "ERRO ao aplicar perfil (daemon offline?)" — o daemon RESPONDEU."""
    stub = _FooterStub()
    resposta["result"] = {"status": "ok", "applied": [], "failed": {}}

    stub.on_apply_draft()

    assert stub.toasts[-1] == "Nada foi aplicado ao controle."


# ---------------------------------------------------------------------------
# Aplicação PARCIAL: "algo entrou" não é "o mouse entrou"
# ---------------------------------------------------------------------------


def test_secao_mouse_que_falhou_mantem_a_pendencia(
    resposta: dict[str, Any], journal: list[dict[str, Any]]
) -> None:
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = {
        "status": "ok",
        "applied": ["leds"],
        "failed": {"mouse": "uinput fechado"},
    }

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is True
    # Algo entrou de fato — o journal não pode dizer que a transação foi vazia.
    assert journal[-1]["ok"] is True


def test_secao_mouse_aplicada_baixa_a_pendencia(resposta: dict[str, Any]) -> None:
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = {"status": "ok", "applied": ["leds", "mouse"], "failed": {}}

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is False
    assert stub.draft.mouse.in_profile is True


# ---------------------------------------------------------------------------
# Sem informação não há do que desconfiar (daemon antigo / bridge cru)
# ---------------------------------------------------------------------------


def test_resposta_sem_applied_continua_contando_como_aplicada(
    resposta: dict[str, Any], journal: list[dict[str, Any]]
) -> None:
    """HARM-05 preservado: o `dirty` continua baixando com daemon que não
    reporta `applied` — a regra é a MESMA que `_mensagem_de_aplicacao` usa."""
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = {"status": "ok"}

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is False
    assert journal[-1]["ok"] is True


def test_bridge_devolvendo_true_cru_continua_valendo(
    resposta: dict[str, Any],
) -> None:
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = True

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is False


def test_status_failed_continua_sendo_recusa(
    resposta: dict[str, Any], journal: list[dict[str, Any]]
) -> None:
    """`status != "ok"` é recusa: frase de erro, `ok=False`, `aceita=False`."""
    stub = _FooterStub()
    _com_mouse_pendente(stub)
    resposta["result"] = {"status": "failed", "applied": ["leds"]}

    stub.on_apply_draft()

    assert stub.draft.mouse.dirty is True
    assert journal[-1]["ok"] is False
    assert journal[-1]["aceita"] is False
    assert stub.toasts[-1] == "ERRO ao aplicar perfil (daemon offline?)."
