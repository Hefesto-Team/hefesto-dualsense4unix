"""STATUS-DIZ-O-QUE-VÊ-01/T4 — o card ordenado tem de receber o registro dele."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status: cada card recebe o seu")

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin as S

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "state_full_quatro_controles.json"


def _mesa_cheia() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _nome(no: Any) -> str:
    """O nome legível de um nó de AST — ``keys``, ``self.x``, ou ``<expr>``."""
    import ast

    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return f"{_nome(no.value)}.{no.attr}"
    if isinstance(no, ast.Call):
        return f"{_nome(no.func)}(...)"
    return "<expr>"


class _AbaDeMentira(S):  # type: ignore[misc]
    """A aba Status reduzida ao que este teste afere: quem recebe o quê."""

    def __init__(self) -> None:
        self._status_cards: dict[Any, Any] = {}
        self._status_card_keys: list[Any] = []
        self.alimentados: list[tuple[Any, dict[str, Any]]] = []


def test_nenhuma_grade_da_aba_casa_as_chaves_com_a_lista_crua() -> None:
    """O portão que teria pego este defeito no dia em que ele nasceu.

    Varredura de FONTE, e não de comportamento: as duas grades vivem em
    funções que pedem GTK, IPC e um `state_full` inteiro para rodar, e um
    teste de comportamento por grade nasceria caro e cobriria uma delas de
    cada vez. A pergunta aqui é sintática e é a certa — *existe algum `zip`
    que case `keys` com a lista crua?* — e ela vale para a grade que a Onda 4
    ainda vai escrever.

    **A mordida:** devolva `zip(keys, conectados, strict=True)` a qualquer uma
    das duas e o portão reprova nomeando arquivo e linha.
    """
    import ast

    fonte = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "hefesto_dualsense4unix"
        / "app"
        / "actions"
        / "status_actions.py"
    )
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    suspeitos = [
        f"status_actions.py:{no.lineno}: zip({', '.join(_nome(a) for a in no.args)})"
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and _nome(no.func) == "zip"
        and [_nome(a) for a in no.args[:2]] == ["keys", "conectados"]
    ]

    assert not suspeitos, (
        "uma grade da aba Status volta a casar as chaves ORDENADAS com a "
        "lista CRUA do daemon, posição a posição — é o defeito de T4, e ele "
        f"alimenta cada card com o registro do vizinho: {suspeitos}"
    )
