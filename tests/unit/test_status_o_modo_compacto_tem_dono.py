"""STATUS-DIZ-O-QUE-VÊ-01/T5 — o modo compacto do card tem de ter um dono."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


def _chamadas_com_compact_verdadeiro() -> list[str]:
    """Toda chamada de produção que passa ``compact=True``, com o endereço."""
    achados: list[str] = []
    for arquivo in sorted(_SRC.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — arquivo quebrado é outro erro
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for palavra in no.keywords:
                if (
                    palavra.arg == "compact"
                    and isinstance(palavra.value, ast.Constant)
                    and palavra.value.value is True
                ):
                    relativo = arquivo.relative_to(_SRC.parents[1])
                    achados.append(f"{relativo}:{no.lineno}")
    return achados


def test_o_modo_compacto_tem_dono() -> None:
    """Ou nenhum código de produção pede o card compacto, ou alguém o pede."""
    chamadas = _chamadas_com_compact_verdadeiro()
    assert not chamadas, (
        "código de produção voltou a construir o card COMPACTO: "
        f"{chamadas}. Desde a EMPILHA-02 (02/08/2026) a aba dá a largura "
        "inteira a todo card — se a volta é intencional, escreva aqui quem "
        "constrói o modo compacto e quando"
    )


def _docstring_do_card_de_producao() -> str:
    """A docstring do `ControllerCard` que a janela monta, lida do FONTE."""
    arquivo = _SRC / "app" / "widgets" / "controller_card.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    cards = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.ClassDef)
        and no.name == "ControllerCard"
        and any(
            isinstance(base, ast.Attribute)
            and isinstance(base.value, ast.Name)
            and base.value.id == "Gtk"
            for base in no.bases
        )
    ]
    assert len(cards) == 1, (
        f"achei {len(cards)} `ControllerCard` herdando do GTK em {arquivo} — a "
        "régua precisa de exatamente um, o que a janela monta. Se o card mudou "
        "de casa ou de base, aponte esta leitura para ele; sem isso ela mediria "
        "o stub, ou nada."
    )
    return ast.get_docstring(cards[0]) or ""


def test_a_docstring_do_card_nao_ensina_o_modo_que_ninguem_constroi() -> None:
    """O exemplo de uso tem de ser o que a aba faz — e era o oposto."""
    doc = _docstring_do_card_de_producao()
    assert "compact=True" not in doc, (
        "a docstring de `ControllerCard` volta a ensinar `compact=True` como "
        "o uso normal. Produção passa `compact=False` desde 02/08/2026, e "
        "este exemplo foi a fonte dos sete arquivos de teste que travam um "
        "desenho que a janela não monta"
    )
    assert "compact=False" in doc, (
        "a docstring de `ControllerCard` parou de mostrar como a aba monta o "
        "card. O exemplo é o que a próxima pessoa copia — ele precisa ser o "
        "que produção faz"
    )


def test_o_alojar_da_rota_nao_promete_o_que_ela_aposentou() -> None:
    """A T9 da sprint parte de uma premissa FALSA, e este teste a fixa."""
    import inspect

    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    doc = inspect.getdoc(StatusActionsMixin._alojar_botao_da_rota) or ""

    assert "SOM-ROTA-NO-CARD-01" not in doc or "CORREÇÃO DE FATO" in doc, (
        "a docstring de `_alojar_botao_da_rota` volta a afirmar que entrega a "
        "SOM-ROTA-NO-CARD-01 sem dizer que aquilo caducou em 02/08/2026. Foi "
        "essa frase que fez uma sprint inteira propor desfazer uma decisão "
        "dela"
    )
    assert "SOM-CANAL-01" in doc, (
        "a docstring de `_alojar_botao_da_rota` não nomeia a decisão que "
        "aposentou o reparenteamento (SOM-CANAL-01/E3, 02/08/2026). Sem o "
        "ponteiro, a próxima pessoa relê o `None` como defeito — foi o que "
        "aconteceu"
    )
