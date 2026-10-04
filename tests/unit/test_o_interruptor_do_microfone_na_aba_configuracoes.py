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
from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    frase_da_capacidade_do_mic,
)
from hefesto_dualsense4unix.interface.dados_do_controle import DadosDoControle
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    PALAVRAS_DE_CULPA,
    SLOTS_POR_SEGUNDO,
)

UM = "aabbcc000001"
DOIS = "aabbcc000002"
OITO_BITDO = "e8473a000007"


def _dados(**over: Any) -> DadosDoControle:
    base: dict[str, Any] = dict(
        chave=UM,
        titulo="Jogador 1",
        subtitulo="Sony · Bluetooth",
        uniq=UM,
        slot=1,
        adotado=True,
        no_cabo=False,
        endereco=UM,
    )
    base.update(over)
    return DadosDoControle(**base)


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


class TestAFraseDeCapacidade:
    def test_a_frase_de_capacidade_e_derivada_do_medidor(self) -> None:
        """Nenhum número digitado: os quatro saem das constantes de `radio_da_mesa`."""
        frase = frase_da_capacidade_do_mic()

        for valor in (HZ_INPUT_SEM_MIC, HZ_INPUT_COM_MIC, HZ_AUDIO_COM_MIC):
            esperado = f"{valor:.1f}".replace(".", ",")
            assert esperado in frase, f"{esperado} não está na frase: {frase!r}"
        assert str(SLOTS_POR_SEGUNDO) in frase

        fonte = Path(inspect.getfile(secao_controles)).read_text(encoding="utf-8")
        corpo = fonte.split("def frase_da_capacidade_do_mic")[1].split("\ndef ")[0]
        for literal in ("260,4", "170,5", "106,2", "276,7"):
            assert literal not in corpo, (
                f"{literal!r} está digitado na frase de capacidade. Ele tem de "
                "sair das constantes de `integrations/radio_da_mesa`, senão a "
                "tela e a barra do medidor podem discordar sobre o mesmo fato."
            )

    def test_a_frase_nao_culpa_o_controle(self) -> None:
        """A mesma lista que o medidor de rádio varre, pela mesma razão."""
        minuscula = frase_da_capacidade_do_mic().lower()
        for palavra in PALAVRAS_DE_CULPA:
            assert palavra not in minuscula, (
                f"a frase de capacidade contém {palavra!r} — ela é informação "
                "de capacidade, não advertência (decisão dela, 22/08/2026)"
            )

    def test_a_frase_nao_ressuscita_o_preco_contra_o_giroscopio(self) -> None:
        """O trade-off contra giroscópio foi DERRUBADO em 22/08/2026."""
        textos = frase_da_capacidade_do_mic().lower()
        for proibida in ("girosc", "mira", "250"):
            assert proibida not in textos, (
                f"{proibida!r} voltou ao texto do interruptor: a comparação "
                "entre a taxa do rádio e a taxa NATIVA DO CABO é a armadilha "
                "nº 1 desta casa, e ela já foi derrubada uma vez"
            )

