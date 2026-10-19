"""O Start da Navegação Interna grava o perfil e o manda aos controles, num gesto só.

Pedido de 19/10/2026: o Options salva e aplica o perfil, como a troca de jogo faz sozinha. Até
aqui ele clicava o «Salvar», que só reaplica quando o perfil já é o que vale.

MORDIDAS:
  * devolva o `ops.append({"op": "salvar"})` ao `_agir`: o Start não chega ao gesto novo;
  * tire o `profile_reaplicar` do `salvar_e_aplicar`: o perfil grava e não vai aos controles.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import navegacao_interna as nav
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, rodape
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from tests.unit.ponte_do_rodape import PonteDoRodape

NOME = "Prova do Start"


class _PonteQuePrende(PonteDoRodape):
    def __init__(self) -> None:
        super().__init__()
        self.prendeu: list[bool] = []

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> dict[str, Any] | None:
        self.prendeu.append(prender)
        return super().profile_reaplicar(nome, prender=prender)


@pytest.fixture
def ctx(monkeypatch: pytest.MonkeyPatch) -> Contexto:
    loader.save_profile(Profile(name=NOME, match=MatchCriteria(window_class=["prova"])),
                        origem="régua")
    return Contexto(state={"active_profile": NOME}, mesa=[], conectados=[], estados={})


def test_o_gesto_grava_e_depois_aplica_prendendo(ctx: Contexto,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1910-O-START-DA-NAVEGACAO-SALVA-E-APLICA: grava, e o último pedido é o reaplicar."""
    ponte = _PonteQuePrende()
    gravar = rodape.perfil.gravar_e_reaplicar

    def gravar_anotando(*a: Any, **k: Any) -> Any:
        ponte.chamadas.append("gravou")
        return gravar(*a, **k)

    monkeypatch.setattr(rodape.perfil, "gravar_e_reaplicar", gravar_anotando)
    gesto = pacotes.gesto_da_pagina("03-gatilhos.html", hv.GESTO_DO_START)
    assert gesto is not None, "o Start não tem dono"
    gesto(ctx, {"gesto": hv.GESTO_DO_START}, ponte)
    assert "gravou" in ponte.chamadas, "o Start não gravou o perfil"
    assert ponte.chamadas[-1] == "profile.reaplicar", ponte.chamadas
    assert ponte.chamadas.index("gravou") < len(ponte.chamadas) - 1
    assert ponte.prendeu[-1] is True, "o perfil foi aos controles sem ficar valendo"


def test_o_gesto_grava_na_fila_de_quem_grava() -> None:
    assert pacotes.GESTOS_QUE_MEXEM.get(("*", hv.GESTO_DO_START)), (
        "sem a fila de quem grava, o Start cruzaria com outro gesto que grava o perfil")


def test_o_start_da_janela_chama_o_gesto(ctx: Contexto) -> None:
    gestos: list[dict[str, Any]] = []
    js: list[str] = []
    piloto = SimpleNamespace(_selecoes=nav.Selecoes(), pagina="04-iluminacao.html",
                             _js=js.append, _com_molduras=False, _ir=lambda p: False,
                             _gesto=gestos.append)
    leiaute = {"largura": 800, "altura": 600, "popup": False, "caixas": []}
    hv.Piloto._agir(piloto, [nav.Ato("salvar")], leiaute, ctx,  # type: ignore[arg-type]
                    {}, {})
    assert [(g["gesto"], g["pagina"]) for g in gestos] == [  # (noqa-acento: chave)
        (hv.GESTO_DO_START, "04-iluminacao.html")], gestos
    assert not any('"salvar"' in linha for linha in js), "o Start ainda clica o «Salvar»"
