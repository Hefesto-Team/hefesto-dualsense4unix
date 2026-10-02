"""A seção "A mesa" leva a declaração dela ao disco — e a relê ao voltar."""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("declaração da mesa")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa, RadioUsb


class _Hospedeiro:
    """O mínimo que a seção toca: o rascunho da máquina, e nada mais."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def _mesa_de_bancada() -> Mesa:
    """Um adaptador e um rádio vizinho — o bastante para as duas tabelas."""
    return Mesa(
        adaptadores=[
            Adaptador(
                interface="hci0",
                no="1-1",
                vid="0a12",
                pid="0001",
                busnum=1,
                devpath="1",
                painel="rear",
            )
        ],
        radios=[
            RadioUsb(no="1-2", vid="046d", pid="c52b", busnum=1, devpath="2")
        ],
    )


def test_a_secao_nao_diz_mais_que_a_camada_de_persistencia_nao_existe() -> None:
    """O comentário caduco é o defeito, não o enfeite dele."""
    from pathlib import Path

    fonte = Path(secao_mesa.__file__).read_text(encoding="utf-8")
    assert "TODO(CONFIG-03)" not in fonte, (
        "o módulo ainda diz que espera CONFIG-03. A camada existe desde "
        "22/08/2026 (`utils/maquina.py` e o `machine.declare` do IPC) — um TODO "
        "que sobrevive à própria cura ensina a próxima pessoa a não ligá-la."
    )


class _SeletorFalso:
    """Só o `get_active_id`, que é tudo o que o gesto lê do widget."""

    def __init__(self, ativo: str | None) -> None:
        self._ativo = ativo

    def get_active_id(self) -> str | None:
        return self._ativo
