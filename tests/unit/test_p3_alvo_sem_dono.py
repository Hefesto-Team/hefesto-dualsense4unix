"""P3 — o alvo sem dono: "Todos" e "não sei" tinham o mesmo valor."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p3 alvo sem dono")

from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    ATRIBUTO_LEGADO_LABEL,
    ATRIBUTO_LEGADO_UNIQ,
    EstadoDoAlvo,
    alvo_de_edicao,
    definir_alvo,
)

UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


class _Janela:
    """Hospedeiro mínimo: só carrega atributos, como a janela real."""


def test_p3_definir_alvo_por_controle_espelha_o_atributo_legado() -> None:
    """Os nove leitores não migrados enxergam o mesmo de sempre."""
    janela = _Janela()
    definir_alvo(janela, UNIQ_2, "Controle 2 (USB)")
    assert alvo_de_edicao(janela).estado is EstadoDoAlvo.CONTROLE
    assert getattr(janela, ATRIBUTO_LEGADO_UNIQ, None) == UNIQ_2
    assert getattr(janela, ATRIBUTO_LEGADO_LABEL, None) == "Controle 2 (USB)"


def test_p3_ponte_le_quem_ainda_escreve_o_atributo_antigo() -> None:
    """Dublê de teste que escreve direto não vira "desconhecido" por engano."""
    janela = _Janela()
    janela._edit_target_uniq = UNIQ_1  # type: ignore[attr-defined]
    janela._edit_target_label = "Controle 1 (BT)"  # type: ignore[attr-defined]
    alvo = alvo_de_edicao(janela)
    assert alvo.estado is EstadoDoAlvo.CONTROLE
    assert alvo.uniq == UNIQ_1

    global_na_mao = _Janela()
    global_na_mao._edit_target_uniq = None  # type: ignore[attr-defined]
    assert alvo_de_edicao(global_na_mao).estado is EstadoDoAlvo.TODOS


class _FakeBadge:
    def __init__(self) -> None:
        self.text = ""
        self.visible = False

    def set_text(self, text: str) -> None:
        self.text = text

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


def _instancia() -> Any:
    inst = StatusActionsMixin.__new__(StatusActionsMixin)
    inst._target_combo = object()
    inst._externals = []
    inst._externals_sig = None
    inst._target_combo_rows = []
    inst._target_combo_active = -1
    inst._target_combo_visible = False
    inst._target_uniq_by_index = {}
    inst._target_label_by_index = {}
    inst._numero_faixa = None
    inst._numero_box = None
    inst._edit_badge = _FakeBadge()
    inst._rebuild_target_buttons = lambda box, rows: None
    inst._set_target_active = lambda pos: None
    inst._set_target_strip_visible = lambda visivel: None
    return inst


def _estado(*controles: dict[str, Any]) -> dict[str, Any]:
    return {"controllers": list(controles), "output_target_index": 0}


def _controle(index: int, uniq: str) -> dict[str, Any]:
    return {
        "index": index,
        "connected": True,
        "transport": "bt",
        "uniq": uniq,
        "player_slot": index + 1,
    }


def test_p3_a_classe_nao_carrega_mais_o_default_global() -> None:
    """A linha do defeito: o atributo de classe respondia por quem não sabia."""
    assert "_edit_target_uniq" not in vars(StatusActionsMixin)
    assert "_edit_target_label" not in vars(StatusActionsMixin)
    crua = StatusActionsMixin.__new__(StatusActionsMixin)
    assert getattr(crua, "_edit_target_uniq", "AUSENTE") == "AUSENTE"


