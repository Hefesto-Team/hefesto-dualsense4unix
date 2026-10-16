"""O-ATIVAR-DA-ABA-PERFIS-AGE-SOBRE-O-PERFIL-QUE-O-EDITOR-MOSTRA-01 — o Ativar e o clique na linha.

Medido antes de curar (12/10/2026): o «Perfil ativo» do cabeçalho dizia um nome e o editor outro,
porque o `ativar` lia o `texto` que o botão manda («Ativar»), e o clique numa linha só ABRIA o
perfil. Desde 15/10 o clique na linha abre E ativa (`profile.switch`), e o botão Ativar age sobre
o perfil do editor. Os esperados abaixo são escritos à mão, e a ponte anota o que o daemon recebeu.

MORDIDAS (cada uma foi feita e viu reprovar):

* ler o `texto` do botão no `ativar` (`or texto`) -> o daemon recebe «Ativar»;
* tirar o `_ativar_o` do `selecionar` -> o clique só abre, e o cabeçalho segue no perfil velho;
* tirar a trava do Freestyle do `selecionar` -> o clique derruba o Freestyle ligado.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile


class Ponte:
    """Anota o que o daemon recebeu; nunca fala com o daemon vivo."""

    def __init__(self) -> None:
        self.trocas: list[str] = []

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        if metodo == "profile.switch":
            self.trocas.append(str(kw.get("name")))
        return {}

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True


@pytest.fixture(autouse=True)
def disco(monkeypatch: pytest.MonkeyPatch) -> None:
    todos = [Profile(name=n, match=MatchAny(), priority=10 - i)
             for i, n in enumerate(("Alfa", "Beta", "Gama"))]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)


def _ctx(ativo: str = "Alfa", **estado: Any) -> Contexto:
    return Contexto(state={"active_profile": ativo, **estado}, mesa=[], conectados=[], estados={})


def test_o_clique_na_linha_abre_e_ativa() -> None:
    """MORDIDA: sem o `_ativar_o` no `selecionar` o daemon não recebe nada."""
    ponte = Ponte()
    resposta = a10_perfis.selecionar(_ctx(), {"hefPerfil": "Beta"}, ponte)
    assert ponte.trocas == ["Beta"]
    assert a10_perfis._ESCOLHIDO == "Beta", "o editor abre no mesmo perfil que foi ativado"
    assert resposta is not None and "Beta" in str(resposta)


def test_o_clique_no_perfil_que_ja_vale_so_abre() -> None:
    ponte = Ponte()
    assert a10_perfis.selecionar(_ctx("Alfa"), {"hefPerfil": "Alfa"}, ponte) is None
    assert ponte.trocas == [] and a10_perfis._ESCOLHIDO == "Alfa"


def test_com_o_freestyle_ligado_o_clique_so_abre() -> None:
    """MORDIDA: sem a trava, o clique derruba o Freestyle que a pessoa ligou."""
    ponte = Ponte()
    assert a10_perfis.selecionar(_ctx(freestyle_ligado=True), {"hefPerfil": "Gama"}, ponte) is None
    assert ponte.trocas == [] and a10_perfis._ESCOLHIDO == "Gama"


def test_o_clique_sem_nome_recusa_sem_chamar_o_daemon() -> None:
    ponte = Ponte()
    with pytest.raises(ValueError, match="nome do perfil"):
        a10_perfis.selecionar(_ctx(), {}, ponte)
    assert ponte.trocas == []


def test_o_ativar_age_sobre_o_perfil_que_o_editor_mostra() -> None:
    """MORDIDA: ler o `texto` do botão manda «Ativar» ao daemon como se fosse um perfil."""
    a10_perfis._ESCOLHIDO = "Gama"
    ponte = Ponte()
    a10_perfis.ativar(_ctx("Alfa"), {"texto": "Ativar"}, ponte)
    assert ponte.trocas == ["Gama"]


def test_o_ativar_recusa_o_perfil_que_ja_vale_sem_chamar_o_daemon() -> None:
    a10_perfis._ESCOLHIDO = "Alfa"
    ponte = Ponte()
    with pytest.raises(RuntimeError, match="já é o perfil que está valendo"):
        a10_perfis.ativar(_ctx("Alfa"), {"texto": "Ativar"}, ponte)
    assert ponte.trocas == []


def test_a_recusa_do_daemon_nao_some() -> None:
    class Calada(Ponte):
        def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
            raise RuntimeError("daemon fora")

    a10_perfis._ESCOLHIDO = "Beta"
    with pytest.raises(RuntimeError, match="não confirmou a troca para 'Beta'"):
        a10_perfis.ativar(_ctx("Alfa"), {}, Calada())
