"""O-PERFIL-APAGADO-ESQUECE-O-POINT-AND-CLICK-QUE-APONTAVA-PARA-ELE-01 (23/10/2026).

Apagar um perfil tirava o nome da escolha do boot e do último jogo, mas deixava o
`perfil:<nome>` do Point and click, no computador e em cada perfil: a cada uso o daemon caía
no `except` do `_tabelas_do_arranjo`, registrava `point_and_click_sem_tabela` e
devolvia a tabela de base, sem aviso na tela. O dono é o `esquecer_o_perfil_apagado`
(`profiles/manager.py`), que usa a mesma passada do renomear. O disco é o de verdade, no lar
isolado da suíte; o gesto é o da aba 10 (o `remover`) e o do `delete_profile`.

Sem a escolha, vale o que vale numa instalação limpa: o perfil segue o computador, e o
computador, o molde Point and click (a ordem de D-2010-O-POINT-AND-CLICK-APLICA-O-PERFIL-ESCOLHIDO).
Gravar o molde no perfil seria uma escolha que a pessoa não fez, por cima da do computador.

A MORDIDA: tire a passada do `esquecer_o_perfil_apagado`, e o campo segue em `perfil:X`.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a06_navegacao, a10_perfis
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


def _o_que_vale(nome: str) -> str:
    """A escolha que vale com ``nome`` ativo, lida pela função da aba Navegação."""
    return a06_navegacao._o_point_and_click_de_hoje(nome)


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
    """Os três que apontavam para X perdem a escolha; o de Y e o sem escolha não mudam.

    MORDIDA: sem a passada no `esquecer_o_perfil_apagado`, os três seguem em `perfil:Sackboy`.
    """
    _montar("perfil:Sackboy")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() is None, "o do computador ficou apontando o apagado"
    assert _do_perfil("Pragmata") is None
    assert _do_perfil("Lure") is None
    assert _do_perfil("Dungeons") == "perfil:Mullet", "o que apontava para outro mudou"
    assert _do_perfil("Calmo") is None, "o que não escolhia ganhou uma escolha"
    assert _o_que_vale("Pragmata") == PADRAO and _o_que_vale("Calmo") == PADRAO


def test_a_escolha_do_computador_que_aponta_para_outro_nao_muda() -> None:
    _montar("perfil:Mullet")
    antes = loader.load_profile("Dungeons").model_dump(mode="json")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() == "perfil:Mullet"
    assert loader.load_profile("Dungeons").model_dump(mode="json") == antes


def test_o_perfil_que_apontava_o_apagado_volta_a_seguir_o_computador() -> None:
    """O computador aponta Y e o perfil apontava X: apagado X, o perfil vale Y, não o molde.

    MORDIDA: gravar o molde no perfil (em vez de tirar a escolha) faz valer o molde por cima da
    escolha do computador.

    Prova da D-2310-O-PERFIL-APAGADO-TIRA-A-ESCOLHA-DO-POINT-AND-CLICK.
    """
    _montar("perfil:Mullet")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_perfil("Pragmata") is None and _do_perfil("Lure") is None
    assert _o_que_vale("Pragmata") == "perfil:Mullet"
    assert _o_que_vale("Lure") == "perfil:Mullet"


def test_a_escolha_escrita_pelo_slug_tambem_volta_ao_padrao() -> None:
    """«sackboy» aponta o mesmo arquivo que «Sackboy» (o `load_profile` acha pelo slug)."""
    _montar("perfil:sackboy")
    loader.delete_profile("Sackboy")

    manager.esquecer_o_perfil_apagado("Sackboy")

    assert _do_computador() is None


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
    assert _do_computador() is None and _do_perfil("Pragmata") is None
    assert _do_perfil("Lure") is None and _do_perfil("Dungeons") == "perfil:Mullet"
    assert _o_que_vale("Pragmata") == PADRAO


def test_o_renomear_e_o_apagado_usam_a_mesma_passada() -> None:
    """Uma função só leva o `perfil:<nome>`; o renomear segue levando ao nome novo."""
    import inspect

    assert callable(manager._levar_o_point_and_click)
    assert "_levar_o_point_and_click(" in inspect.getsource(manager.esquecer_o_perfil_apagado)
    assert "_levar_o_point_and_click(" in inspect.getsource(manager.levar_o_perfil_renomeado)

    _montar("perfil:Sackboy")
    manager.levar_o_perfil_renomeado("Sackboy", "Sackboy 2")
    assert _do_computador() == "perfil:Sackboy 2" and _do_perfil("Lure") == "perfil:Sackboy 2"
