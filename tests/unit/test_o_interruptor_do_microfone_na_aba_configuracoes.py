"""QUATRO-MICROFONES-01 (E1) — o interruptor de microfone existe, num card só."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o interruptor de microfone da seção Os controles")

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_controles

UM = "aabbcc000001"
DOIS = "aabbcc000002"
OITO_BITDO = "e8473a000007"


def _assentar() -> None:
    for _ in range(200):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()


def _rotulos(widget: Any, achados: list[str] | None = None) -> list[str]:
    """Todo texto visível na árvore — é assim que se pergunta "está na tela?"."""
    achados = [] if achados is None else achados
    with_label = getattr(widget, "get_label", None)
    if callable(with_label):
        texto = with_label()
        if texto:
            achados.append(str(texto))
    filhos = getattr(widget, "get_children", None)
    if callable(filhos):
        for filho in filhos():
            _rotulos(filho, achados)
    return achados


class _HostFalso:
    """O `HefestoApp` reduzido ao que a seção lê — sem GTK e sem daemon."""

    def __init__(self, controles: list[dict[str, Any]]) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._edit_target_uniq: str | None = None
        self._controles_leitor = lambda: {"controllers": controles, "external": []}
        self._cor_do_plastico_leitor = lambda _u: None
        self._mesa_limpa_leitor = lambda: False


def _entrada(uniq: str, *, transporte: str = "bt") -> dict[str, Any]:
    return {
        "uniq": uniq,
        "transport": transporte,
        "connected": True,
        "player_slot": 1 if uniq == UM else 2,
        "name": "Sony Interactive Entertainment Wireless Controller",
        "vid": "054c",
        "pid": "0ce6",
    }


class TestOGesto:


    def test_a_secao_nao_manda_ipc_nenhum_no_clique(self) -> None:
        """Nenhum `machine.declare` e nenhuma chamada a `dualsense_bt_audio`."""
        fonte = Path(inspect.getfile(secao_controles)).read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        chamadas = {
            no.func.attr
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        }
        assert "machine_declare" not in chamadas
        importados = {
            alvo
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom) and no.module
            for alvo in (no.module,)
        } | {
            nome.name
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for nome in no.names
        }
        assert not any("dualsense_bt_audio" in mod for mod in importados), (
            "a seção importou o módulo da ponte de áudio: o processo da janela "
            "não pode subir um microfone a um clique de distância enquanto a "
            "posse do hidraw não for arbitrada"
        )
