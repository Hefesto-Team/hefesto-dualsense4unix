"""Cada quadrado da janela do mapa diz se o aparelho fica bem ali."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o juízo de cada quadrado do mapa 2D")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.interface.logica_do_mapa import LogicaDoMapa, ensaio_do_rascunho
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_mapa_o_ensaio_de_mentira import (
    ensaio_de_agora,
    mapa_do_usuario,
)

BT_DA_EXTENSAO = "3-1.1.4"

ENTRADA_DO_BT_DO_HUB = "13"

ENTRADA_COLADA_NO_BT = "14"


class _Hospedeiro:
    """O mínimo que a janela toca no hospedeiro — o rascunho e a marca."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcou = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcou += 1


def test_o_ensaio_do_rascunho_responde_com_o_gabinete_vazio() -> None:
    """Quem nunca desenhou não recebe juízo nenhum, e também não recebe erro."""
    ensaio = ensaio_do_rascunho(LogicaDoMapa(MapaDaMesa()), ensaio_de_agora().censo())

    assert ensaio.mesa.faces == ()
    assert mapa_das_portas.LACUNA_POSICAO not in ensaio.lacunas, (
        "sem face nenhuma não há fileira, e confessar a posição de entradas que "
        f"não existem é ruído: {ensaio.lacunas}"
    )


def test_o_rascunho_nao_derruba_o_que_so_o_usuario_sabe_da_face() -> None:
    """`perto` e `alto` atravessam o rascunho — senão o "Aplicar" os apagaria."""
    bruto = mapa_do_usuario().model_dump(mode="json")
    bruto["faces"][0]["perto"] = True
    bruto["faces"][2]["alto"] = True
    mapa = MapaDaMesa.model_validate(bruto)

    logica = LogicaDoMapa(mapa)
    logica.escolher("1-3")
    logica.colocar("3")
    documento = logica.como_documento()

    assert documento["faces"][0].get("perto") is True, (
        "a face marcada como a mais perto voltou do rascunho sem o "
        f"fato marcado: {documento['faces'][0]}"
    )
    assert documento["faces"][2].get("alto") is True, (
        "a face marcada como a do alto voltou do rascunho sem o fato "
        f"marcado: {documento['faces'][2]}"
    )
    ensaio = ensaio_do_rascunho(logica, ensaio_de_agora().censo())
    assert ensaio.mesa.faces[0].perto is True
    assert ensaio.mesa.faces[2].alto is True


def _todo_o_texto(widget: Any) -> set[str]:
    """Todo rótulo da árvore de widgets, para conferir o que a tela DIZ."""
    achados: set[str] = set()
    pilha = [widget]
    while pilha:
        atual = pilha.pop()
        obter = getattr(atual, "get_text", None)
        if obter is not None and getattr(atual, "get_line_wrap", None) is not None:
            achados.add(str(obter()))
        filhos = getattr(atual, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados
