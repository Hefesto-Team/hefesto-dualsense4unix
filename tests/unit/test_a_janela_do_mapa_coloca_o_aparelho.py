"""A janela do mapa põe o aparelho na entrada, e o desenho espera o "Aplicar"."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a janela do mapa 2D")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.interface.logica_do_mapa import LogicaDoMapa
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
)
from tests.unit.test_mapa_a_bancada_de_mentira import mapa_dela


class _Hospedeiro:
    """O mínimo que a janela toca no hospedeiro — o rascunho e a marca."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcou = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcou += 1


def test_a_segunda_extensao_da_mesma_entrada_ganha_outra_letra() -> None:
    """Duas extensões na mesma entrada são ``12a`` e ``12b``, nunca a mesma."""
    logica = LogicaDoMapa(mapa_dela())

    assert logica.acrescentar_extensao("12") == "12a"
    assert logica.acrescentar_extensao("12") == "12b"
    assert sorted(logica.filhas_de("12")) == ["12a", "12b"]


def test_acrescentar_face_pede_um_nome() -> None:
    """Face sem nome não nasce — um quadrado sem rótulo não se acha no metal."""
    logica = LogicaDoMapa(MapaDaMesa())

    assert logica.acrescentar_face("   ") is False
    assert logica.faces == []
    assert logica.acrescentar_face("Esquerda") is True
    assert logica.acrescentar_face("Direita") is True
    assert [face["nome"] for face in logica.faces] == ["Esquerda", "Direita"]


def test_a_entrada_nova_nunca_repete_um_numero_do_gabinete() -> None:
    """Os números são do metal: dois buracos não podem ter o mesmo."""
    logica = LogicaDoMapa(MapaDaMesa())
    logica.acrescentar_face("Esquerda")
    logica.acrescentar_face("Direita")

    assert logica.acrescentar_entrada(0) == "1"
    assert logica.acrescentar_entrada(0) == "2"
    assert logica.acrescentar_entrada(1) == "3", (
        "a segunda face repetiu um número que a primeira já usava"
    )


