"""O-PERFIL-APAGADO-ESQUECE-O-POINT-AND-CLICK-QUE-APONTAVA-PARA-ELE-01 (23/10/2026).

Apagar um perfil tirava o nome da escolha do boot e do último jogo, mas deixava o
`perfil:<nome>` do Point and click, no computador e em cada perfil: a cada uso o daemon caía
no `except` do `_tabela_do_point_and_click`, registrava `point_and_click_sem_tabela` e
devolvia a tabela de base, sem aviso na tela. O dono é o `esquecer_o_perfil_apagado`
(`profiles/manager.py`), que usa a mesma passada do renomear. O disco é o de verdade, no lar
isolado da suíte; o gesto é o da aba 10 (o `remover`) e o do `delete_profile`.

A MORDIDA: tire a passada do `esquecer_o_perfil_apagado`, e o campo segue em `perfil:X`.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader, manager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils import maquina

PADRAO = "molde:point_and_click"


class _Ponte:
    """O daemon calado que confirma: nada do aparelho entra na régua."""

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        return True

    def resultado(self, metodo: str, *_a: Any, **_k: Any) -> Any:
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)


def _no_disco(nome: str, point_and_click: str | None = None, prioridade: int = 50) -> None:
    dados: dict[str, Any] = {
        "name": nome, "match": MatchAny().model_dump(), "priority": prioridade,
        "button_actions": {"cross": "BTN_LEFT"},
    }
    if point_and_click is not None:
        dados["mouse"] = {"enabled": False, "point_and_click": point_and_click}
    loader.save_profile(Profile.model_validate(dados), origem="regua")


def _do_computador() -> str | None:
    mouse = maquina.carregar_maquina().computador.global_.mouse
    return None if mouse is None else mouse.point_and_click


def _do_perfil(nome: str) -> str | None:
    mouse = loader.load_profile(nome).mouse
    return None if mouse is None else mouse.point_and_click


def _montar(escolha_do_computador: str) -> None:
    """O computador e dois perfis apontam para X, um terceiro para Y, um quarto para nada."""
    _no_disco("Pragmata", "perfil:Sackboy", 90)
    _no_disco("Lure", "perfil:Sackboy", 80)
    _no_disco("Dungeons", "perfil:Mullet", 70)
    _no_disco("Calmo", None, 60)
    _no_disco("Sackboy", None, 10)
    assert maquina.gravar_o_computador(
        {"global": {"mouse": {"point_and_click": escolha_do_computador}}})
    assert _do_computador() == escolha_do_computador


def test_apagar_leva_ao_padrao_o_computador_e_cada_perfil_que_apontava() -> None:
    """Os três que apontavam para X voltam ao padrão; o de Y e o sem escolha não mudam.

    MORDIDA: sem a passada no `esquecer_o_perfil_apagado`, os três seguem em `perfil:Sackboy`.
    """
    _montar("perfil:Sackboy")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() == PADRAO, "o do computador ficou apontando o apagado"
    assert _do_perfil("Pragmata") == PADRAO
    assert _do_perfil("Lure") == PADRAO
    assert _do_perfil("Dungeons") == "perfil:Mullet", "o que apontava para outro mudou"
    assert _do_perfil("Calmo") is None, "o que não escolhia ganhou uma escolha"


def test_a_escolha_do_computador_que_aponta_para_outro_nao_muda() -> None:
    _montar("perfil:Mullet")
    antes = loader.load_profile("Dungeons").model_dump(mode="json")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() == "perfil:Mullet"
    assert loader.load_profile("Dungeons").model_dump(mode="json") == antes


def test_a_escolha_escrita_pelo_slug_tambem_volta_ao_padrao() -> None:
    """«sackboy» aponta o mesmo arquivo que «Sackboy» (o `load_profile` acha pelo slug)."""
    _montar("perfil:sackboy")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() == PADRAO


def test_a_aba_remover_leva_o_point_and_click_ao_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gesto da aba 10 (o «Remover», no segundo clique) passa pelo mesmo dono."""
    _montar("perfil:Sackboy")
    monkeypatch.setattr(a10_perfis, "_perfil_do_editor", lambda ctx: "Sackboy")
    ctx = Contexto(state={"active_profile": "Pragmata"}, mesa=[], conectados=[], estados={})

    with pytest.raises(RuntimeError, match="Clique em Remover de novo"):
        a10_perfis.remover(ctx, {}, _Ponte())
    a10_perfis.remover(ctx, {}, _Ponte())

    with pytest.raises(FileNotFoundError):
        loader.load_profile("Sackboy")
    assert _do_computador() == PADRAO and _do_perfil("Pragmata") == PADRAO
    assert _do_perfil("Lure") == PADRAO and _do_perfil("Dungeons") == "perfil:Mullet"


def test_o_renomear_e_o_apagado_usam_a_mesma_passada() -> None:
    """Uma função só leva o `perfil:<nome>`; o renomear segue levando ao nome novo."""
    import inspect

    assert callable(manager._levar_o_point_and_click)
    assert "_levar_o_point_and_click(" in inspect.getsource(manager.esquecer_o_perfil_apagado)
    assert "_levar_o_point_and_click(" in inspect.getsource(manager.levar_o_perfil_renomeado)

    _montar("perfil:Sackboy")
    manager.levar_o_perfil_renomeado("Sackboy", "Sackboy 2")
    assert _do_computador() == "perfil:Sackboy 2" and _do_perfil("Lure") == "perfil:Sackboy 2"
