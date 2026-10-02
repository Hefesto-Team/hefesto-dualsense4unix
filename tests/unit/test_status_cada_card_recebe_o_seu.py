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


def test_cada_card_recebe_o_registro_do_proprio_controle() -> None:
    """A MORDIDA: troque `_conectados_na_ordem_dos_cards(conectados)` de volta
    por `conectados` no `parear` (e nas duas grades de produção) e o teste
    reprova nomeando, controle a controle, qual `uniq` estava na chave e qual
    chegou no registro.

    A fixture serve porque a mesa dela está fora de ordem de propósito:
    ``player_slot`` 4, 1, 3, 2 na ordem de enumeração do daemon.
    """
    pares = _AbaDeMentira().parear(_mesa_cheia())

    errados = [
        {
            "posição": pos,
            "uniq na chave": key[1],
            "uniq no registro": entry.get("uniq"),
            "player_slot que a tela vai imprimir": entry.get("player_slot"),
        }
        for pos, (key, entry) in enumerate(pares)
        if key[1] != entry.get("uniq")
    ]

    assert not errados, (
        "card alimentado com o registro de OUTRO controle — a chave diz um "
        f"aparelho e o dado é de outro: {errados}"
    )


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
