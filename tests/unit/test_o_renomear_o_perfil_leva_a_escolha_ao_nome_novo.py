"""O-RENOMEAR-O-PERFIL-LEVA-A-ESCOLHA-AO-NOME-NOVO-01 (21/10/2026).

Renomear pela aba Perfis gravava o nome novo e apagava o velho, e as lembranças ficavam no velho: a
escolha do boot, o último jogo e a escolha do Point and click (a do computador e a de cada perfil)
apontavam para um perfil que deixou de existir com aquele nome. O dono que as leva é o
`levar_o_perfil_renomeado`, ao lado do `esquecer_o_perfil_apagado` (`profiles/manager.py`).
O disco é o de verdade, no lar isolado da suíte; os gestos são os da aba 10 e da aba 06.

A MORDIDA: tire o `levar_o_perfil_renomeado` do `perfis_renomear` (a10), e as lembranças ficam no
nome velho.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import Contexto, a06_navegacao, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils import session


class _Ponte:
    """O daemon calado que confirma: nada do aparelho entra na régua."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        self.chamadas.append(f"profile_reaplicar:{nome}")
        return True

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append(metodo)
        return True

    def resultado(self, metodo: str, *_a: Any, **_k: Any) -> Any:
        self.chamadas.append(metodo)
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a06_navegacao, "_A_MAQUINA", None, raising=False)


def _ctx(ativo: str | None = None) -> Contexto:
    return Contexto(state={"active_profile": ativo} if ativo else {}, mesa=[], conectados=[],
                    estados={})


def _no_disco(*nomes: str) -> None:
    for i, nome in enumerate(nomes):
        loader.save_profile(Profile.model_validate({
            "name": nome, "match": MatchAny().model_dump(), "priority": 100 - i,
            "button_actions": {"cross": "BTN_LEFT"}}), origem="regua")


def _escolher_no_point_and_click(valor: str, ativo: str | None = None) -> None:
    """O gesto da aba 06: sem jogo vai ao computador, com jogo vai ao perfil dele."""
    a06_navegacao.point_and_click_perfil(_ctx(ativo), {"valor": valor}, _Ponte())


def _do_computador() -> str | None:
    from hefesto_dualsense4unix.utils import maquina

    mouse = maquina.carregar_maquina().computador.global_.mouse
    return None if mouse is None else mouse.point_and_click


def _do_perfil(nome: str) -> str | None:
    mouse = loader.load_profile(nome).mouse
    return None if mouse is None else mouse.point_and_click


def _lembrar_tudo(nome: str) -> None:
    """O Point and click antes da escolha: com ela gravada, o gesto sem jogo iria a ela."""
    _escolher_no_point_and_click(f"perfil:{nome}")
    _escolher_no_point_and_click(f"perfil:{nome}", ativo="Pragmata")
    session.gravar_a_escolha(nome)
    session.lembrar_o_ultimo_jogo(nome)
    assert session.load_last_profile() == nome and session._ultimo_jogo_cru() == nome
    assert _do_computador() == f"perfil:{nome}" and _do_perfil("Pragmata") == f"perfil:{nome}"


def _renomear(era: str, novo: str, ponte: _Ponte | None = None) -> None:
    a10_perfis.perfis_renomear(_ctx("Pragmata"), {"valor": novo, "hefPerfil": era},
                               ponte or _Ponte())


def test_renomear_pela_aba_leva_as_lembrancas_ao_nome_novo() -> None:
    """A escolha do boot, o último jogo e as duas escolhas do Point and click seguem o nome.

    A prova da D-2110-O-RENOMEAR-LEVA-AS-LEMBRANCAS-AO-NOME-NOVO.
    """
    _no_disco("Pragmata", "Sackboy", "Lure")
    _lembrar_tudo("Sackboy")

    _renomear("Sackboy", "Sackboy 2")

    with pytest.raises(FileNotFoundError):
        loader.load_profile("Sackboy")
    assert session.load_last_profile() == "Sackboy 2", "a escolha do boot ficou no nome velho"
    assert session.read_active_marker() == "Sackboy 2", "o espelho da escolha ficou no velho"
    assert session._ultimo_jogo_cru() == "Sackboy 2", "o último jogo ficou no nome velho"
    assert _do_computador() == "perfil:Sackboy 2", "o Point and click do computador ficou"
    assert _do_perfil("Pragmata") == "perfil:Sackboy 2", "o Point and click do jogo ficou"
    assert _do_perfil("Lure") is None, "o perfil que não escolhia ganhou uma escolha"
    assert a06_navegacao._o_point_and_click_de_hoje("Pragmata") == "perfil:Sackboy 2"
    assert a06_navegacao._o_point_and_click_de_hoje() == "perfil:Sackboy 2"
    meus = a06_navegacao.pacote(_ctx("Pragmata"))["blocos"]['[data-bloco="meus-perfis"]']
    assert 'value="perfil:Sackboy 2"' in meus, "a lista da 06 não tem a opção que vale"


def test_o_perfil_que_escolhe_a_si_mesmo_segue_o_proprio_nome() -> None:
    """O renomeado que se escolhe no Point and click não fica apontando o arquivo que saiu."""
    _no_disco("Pragmata", "Sackboy")
    _escolher_no_point_and_click("perfil:Sackboy", ativo="Sackboy")

    _renomear("Sackboy", "Sackboy 2")

    assert _do_perfil("Sackboy 2") == "perfil:Sackboy 2"


def test_renomear_outro_perfil_nao_toca_as_lembrancas() -> None:
    _no_disco("Pragmata", "Sackboy", "Lure")
    _lembrar_tudo("Sackboy")
    antes = loader.load_profile("Pragmata").model_dump(mode="json")

    _renomear("Lure", "Lure 2")

    assert session.load_last_profile() == "Sackboy" and session._ultimo_jogo_cru() == "Sackboy"
    assert _do_computador() == "perfil:Sackboy"
    assert loader.load_profile("Pragmata").model_dump(mode="json") == antes


def test_trocar_so_a_caixa_do_nome_tambem_leva_as_lembrancas() -> None:
    """Mesmo arquivo (o slug não muda): a lembrança diz o nome que o perfil tem agora."""
    _no_disco("Pragmata", "Sackboy")
    _lembrar_tudo("Sackboy")

    _renomear("Sackboy", "SackBoy")

    assert session.load_last_profile() == "SackBoy" and session._ultimo_jogo_cru() == "SackBoy"
    assert _do_computador() == "perfil:SackBoy" and _do_perfil("Pragmata") == "perfil:SackBoy"


def test_a_lembranca_escrita_pelo_slug_tambem_segue_o_nome_novo() -> None:
    """A lembrança que diz «sackboy» aponta o mesmo arquivo que «Sackboy» (`load_profile` acha
    pelo slug), então ela também vai ao nome novo: o dono casa pelo slug, como o apagado."""
    from hefesto_dualsense4unix.utils import maquina

    _no_disco("Pragmata", "Sackboy")
    assert maquina.gravar_o_computador(
        {"global": {"mouse": {"point_and_click": "perfil:sackboy"}}})
    session.save_last_profile("sackboy")
    session.lembrar_o_ultimo_jogo("sackboy")

    _renomear("Sackboy", "Sackboy 2")

    assert session.load_last_profile() == "Sackboy 2"
    assert session._ultimo_jogo_cru() == "Sackboy 2"
    assert _do_computador() == "perfil:Sackboy 2"


def test_a_aba_renomeia_pelo_dono_ao_lado_do_que_esquece_o_apagado() -> None:
    """Um dono só para levar as lembranças: o mesmo módulo do `esquecer_o_perfil_apagado`."""
    import inspect

    from hefesto_dualsense4unix.profiles import manager

    assert callable(manager.levar_o_perfil_renomeado)
    assert "levar_o_perfil_renomeado(" in inspect.getsource(a10_perfis.perfis_renomear)
