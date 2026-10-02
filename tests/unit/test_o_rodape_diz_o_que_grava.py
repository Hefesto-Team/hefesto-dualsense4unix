"""O rodapé promete o que faz — T4, CONFIGURAÇÕES-FECHA-01."""
from __future__ import annotations

import inspect
from pathlib import Path

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.config import moldura, secoes

RAIZ = Path(__file__).resolve().parents[2]


def _secoes_que_prometem_o_footer() -> list[str]:
    """As seções cujo módulo importa/usa `QUANDO_VALE` — a promessa do botão."""
    prometem = []
    for secao in secoes.SECOES_DA_ABA:
        fonte = inspect.getsource(secao)
        if "QUANDO_VALE" in fonte:
            prometem.append(secao.TITULO)
    return prometem


def test_pelo_menos_uma_secao_promete_o_footer_hoje() -> None:
    """Régua provada acertando: sem isto, o teste abaixo checaria o vazio."""
    assert _secoes_que_prometem_o_footer(), (
        "nenhuma seção usa QUANDO_VALE — a mordida abaixo não provaria nada"
    )


def test_moldura_ainda_declara_quando_vale() -> None:
    """`QUANDO_VALE` existe e fala do "Aplicar" — a base de que este portão parte."""
    assert "Aplicar" in moldura.QUANDO_VALE
