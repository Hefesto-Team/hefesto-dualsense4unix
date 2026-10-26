"""A receita do tato se lê sem semear nem varrer — 09/10/2026.

O laço do tato vivo roda a 60 Hz no daemon e relê a receita do perfil ativo uma vez
por segundo. Ele lia por `load_profile`, o leitor da tela, que semeia perfis de jogo
(`_talvez_semear_jogos`) e, quando o nome não tem arquivo com o slug dele, varre e
valida todo `*.json` (`arquivo_do_perfil`). A cura lê por `perfil_em_disco`, o mesmo
dono do ganho da háptica, e cai no `load_profile` uma vez por nome.

MORDIDA: volte `receita_ativa` ao `carregar_o_que_vale(nome)` por segundo e os
contadores sobem.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.slug import slugify

TIQUES = 120


@pytest.fixture
def contas(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Os dois caminhos caros contados, cada um chamando o de verdade por baixo."""
    conta = {"semear": 0, "varrer": 0}
    semear, varrer = loader._talvez_semear_jogos, loader.arquivo_do_perfil

    def _semear(*a: Any, **kw: Any) -> Any:
        conta["semear"] += 1
        return semear(*a, **kw)

    def _varrer(*a: Any, **kw: Any) -> Any:
        conta["varrer"] += 1
        return varrer(*a, **kw)

    monkeypatch.setattr(loader, "_talvez_semear_jogos", _semear)
    monkeypatch.setattr(loader, "arquivo_do_perfil", _varrer)
    monkeypatch.setattr(tv, "_PELO_CARREGADOR", None)
    return conta


def _daemon(nome: str) -> Any:
    return SimpleNamespace(store=SimpleNamespace(active_profile=nome))


def _laco(passo: tv.Passo, desde: float = 0.0) -> float:
    agora = desde
    for _ in range(TIQUES):
        passo.tique_do_laco(agora)
        agora += tv.INTERVALO_S
    return agora


def _tiro(nome: str = "Tiro") -> Profile:
    perfil = Profile(name=nome, match=MatchCriteria(window_class=["tiro"]), estilo="fps")
    loader.save_profile(perfil, origem="régua")
    return perfil


FPS = tv.receita_do_estilo(POR_CHAVE["fps"])


def test_o_laco_le_a_receita_sem_semear_nem_varrer(contas: dict[str, int]) -> None:
    """120 tiques com o perfil no arquivo do slug: zero semeadura, zero varredura."""
    _tiro()
    assert FPS.ligada, "o FPS deixou de ter receita: a régua não mede mais nada"
    passo = tv.Passo(_daemon("Tiro"), tv.TatoVivo([]))

    _laco(passo)

    assert contas == {"semear": 0, "varrer": 0}, contas
    assert passo.receita_vigente == FPS


def test_o_orfao_varre_uma_vez_por_nome(contas: dict[str, int]) -> None:
    """Nome sem arquivo com o slug: uma varredura, e outra só quando o nome muda."""
    _tiro("Tiro Antigo")
    pasta = loader.profiles_dir()
    (pasta / f"{slugify('Tiro Antigo')}.json").rename(pasta / "renomeado-por-fora.json")
    daemon = _daemon("Tiro Antigo")
    passo = tv.Passo(daemon, tv.TatoVivo([]))

    agora = _laco(passo)
    assert contas["varrer"] == 1, f"o órfão varreu {contas['varrer']} vezes em 2 s"
    assert passo.receita_vigente == FPS, "a receita do arquivo achado pela varredura sumiu"

    daemon.store.active_profile = "Ninguém"
    _laco(passo, agora)
    assert contas["varrer"] == 2, "o nome novo não foi procurado, ou foi mais de uma vez"
    assert passo.receita_vigente == tv.DESLIGADA


def test_o_perfil_que_volta_ao_slug_e_relido(contas: dict[str, int]) -> None:
    """Quando o arquivo com o slug aparece, a leitura volta a ser a do arquivo."""
    daemon = _daemon("Tiro")
    passo = tv.Passo(daemon, tv.TatoVivo([]))
    agora = _laco(passo)
    assert passo.receita_vigente == tv.DESLIGADA

    _tiro()
    _laco(passo, agora)
    assert passo.receita_vigente == FPS, "o perfil que nasceu com o slug não foi lido"
