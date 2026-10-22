"""O piloto da Sistema pinta o Status e o exame em três colunas, pela conta do produto.

O-PILOTO-DA-SISTEMA-PINTA-O-EXAME-EM-TRES-COLUNAS-01 (17/10/2026): o produto monta o Status e o
exame como UMA lista em três colunas (8 linhas viram 3, 3 e 2, `em_tres_colunas` do a09), e o piloto
`sistema_viva.py` ainda dividia o exame em duas metades (`Math.ceil(n/2)`) sobre uma primeira coluna
que não entrava na conta: 2 + 6 linhas saíam 2, 3 e 3. Agora o Python entrega `colunas`, e a
página só desenha.

MORDIDA: troque `a09.em_tres_colunas(...)` em `_em_colunas` por uma divisão em duas metades, ou
devolva o `Math.ceil` ao JS: os testes abaixo reprovam, cada um pelo seu lado.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("gi")

PILOTOS = Path(__file__).resolve().parents[2] / "scripts" / "tela"


def _piloto() -> Any:
    if str(PILOTOS) not in sys.path:
        sys.path.insert(0, str(PILOTOS))
    import sistema_viva

    return sistema_viva


def _linha(ident: str) -> dict[str, str]:
    return {"id": ident, "cls": "ok", "g": "✓", "selo": "OK", "txt": ident, "dica": ""}


def _achado(n: int) -> dict[str, str]:
    return {"cls": "ok", "g": "✓", "selo": "OK", "txt": f"achado {n}"}


def _pacote(achados: int) -> dict[str, Any]:
    return {
        "status": [_linha("hefesto-estado"), _linha("hefesto-troca-de-perfil"),
                   _linha("status-ambiente"), _linha("status-bluetooth")],
        "exame": {"linhas": [_achado(i) for i in range(achados)], "vazio": "nada"},
    }


def test_oito_linhas_viram_tres_tres_e_duas() -> None:
    """Duas do Status e seis do exame: 3, 3 e 2, e não 2, 3 e 3."""
    colunas = _piloto()._em_colunas(_pacote(6))
    assert [len(c) for c in colunas] == [3, 3, 2]
    assert [x.get("id") for x in colunas[0]][:2] == ["hefesto-estado", "hefesto-troca-de-perfil"]


def test_so_entram_as_linhas_do_status_que_o_campo_leva() -> None:
    """As outras duas do Status (ambiente e Bluetooth) chegam pelo exame, como no produto."""
    colunas = _piloto()._em_colunas(_pacote(2))
    ids = [x.get("id") for c in colunas for x in c if x.get("id")]
    assert ids == ["hefesto-estado", "hefesto-troca-de-perfil"]
    assert sum(len(c) for c in colunas) == 4


def test_sem_achados_o_status_fica_na_primeira_coluna() -> None:
    colunas = _piloto()._em_colunas(_pacote(0))
    assert [len(c) for c in colunas] == [2, 0, 0]


def test_a_conta_e_a_do_pacote_da_aba() -> None:
    """A repartição é a `em_tres_colunas` do a09: a conta tem UM dono."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    for achados in range(1, 10):
        esperado = [len(c) for c in a09.em_tres_colunas(list(range(2 + achados)))]
        assert [len(c) for c in _piloto()._em_colunas(_pacote(achados))] == esperado, achados


def test_o_js_nao_conta_de_novo_e_desenha_as_tres() -> None:
    """A página só desenha o que o Python entregou: sem `Math.ceil`, com as três caixas."""
    js = (PILOTOS / "sistema_viva.py").read_text(encoding="utf-8")
    exame = js[js.index("function exame(p)"):js.index("function pinta(p)")]
    assert "Math.ceil" not in exame and "/ 2" not in exame, "o JS voltou a dividir o exame"
    assert re.search(r"end\('status-lista'\)", exame), "a primeira coluna é o campo do Status"
    assert "p.colunas" in exame, "o JS tem de desenhar as colunas do Python"
