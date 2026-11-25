"""D-2511-O-MAPA-DO-CONTROLE-NAO-RELE-OS-PERFIS: o tique só abre o perfil que mudou no disco.

Sessenta perfis numa pasta de mentira, trinta tiques do `a13.pacote`: depois do primeiro, nenhum
arquivo de perfil é aberto e o tique cabe no teto da casa. O perfil gravado no meio aparece no tique
seguinte, e o que saiu da pasta sai da lista.
"""
from __future__ import annotations

import builtins
import pathlib
import statistics
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, perfil
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

PERFIS = 60
TIQUES = 30
TETO_DA_MEDIANA_MS = 15.0
TROCA = {"cross": "circle", "l1": "r1"}


def _grava(nome: str, **campos: Any) -> None:
    loader.save_profile(Profile(name=nome, match=MatchManual(), **campos))


def _ctx() -> Any:
    return Contexto(state={"active_profile": "Perfil 00"}, mesa=[], conectados=[],
                    escolhido="todos")


@pytest.fixture
def pasta_cheia() -> Iterator[pathlib.Path]:
    for i in range(PERFIS):
        _grava(f"Perfil {i:02d}", remapeamento=TROCA)
    a13._largar()
    yield perfil.pasta()  # type: ignore[misc]
    a13._largar()


@pytest.fixture
def aberturas(monkeypatch: pytest.MonkeyPatch, pasta_cheia: pathlib.Path) -> list[str]:
    """Os arquivos de perfil que o código abre, pelo `Path.read_text` e pelo `open`."""
    abertos: list[str] = []
    ler = pathlib.Path.read_text
    abrir = builtins.open

    def read_text(self: pathlib.Path, *args: Any, **kw: Any) -> str:
        abertos.append(str(self))
        return ler(self, *args, **kw)

    def open_(arq: Any, *args: Any, **kw: Any) -> Any:
        abertos.append(str(arq))
        return abrir(arq, *args, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    monkeypatch.setattr(builtins, "open", open_)
    return abertos


def _de_perfil(abertos: list[str], pasta: pathlib.Path) -> list[str]:
    return [a for a in abertos if a.startswith(str(pasta)) and a.endswith(".json")]


def test_depois_do_primeiro_tique_nenhum_perfil_e_aberto(
        pasta_cheia: pathlib.Path, aberturas: list[str]) -> None:
    ctx = _ctx()
    a13.pacote(ctx)
    assert len(_de_perfil(aberturas, pasta_cheia)) >= PERFIS
    aberturas.clear()
    for _ in range(TIQUES):
        a13.pacote(ctx)
    assert _de_perfil(aberturas, pasta_cheia) == []


def test_o_tique_com_dezenas_de_perfis_cabe_no_teto(
        pasta_cheia: pathlib.Path) -> None:
    ctx = _ctx()
    for _ in range(3):
        a13.pacote(ctx)
    custos = []
    for _ in range(TIQUES):
        t0 = time.thread_time()
        a13.pacote(ctx)
        custos.append((time.thread_time() - t0) * 1000)
    assert statistics.median(custos) < TETO_DA_MEDIANA_MS, (
        f"mediana {statistics.median(custos):.1f} ms com {PERFIS} perfis")


def test_o_perfil_gravado_no_meio_aparece_no_tique_seguinte(pasta_cheia: pathlib.Path) -> None:
    ctx = _ctx()
    _grava("Perfil novo")
    opcoes = a13.pacote(ctx)["blocos"][a13.BLOCO_DO_PERFIL]
    assert "Perfil novo" not in opcoes
    _grava("Perfil novo", remapeamento=TROCA)
    opcoes = a13.pacote(ctx)["blocos"][a13.BLOCO_DO_PERFIL]
    assert "Perfil novo" in opcoes


def test_o_perfil_regravado_com_o_mesmo_tamanho_e_lido_de_novo(pasta_cheia: pathlib.Path) -> None:
    antes = perfil.ativo("Perfil 07")
    assert antes["remapeamento"] == TROCA
    _grava("Perfil 07", remapeamento={"cross": "square", "l1": "r2"})
    assert perfil.ativo("Perfil 07")["remapeamento"] == {"cross": "square", "l1": "r2"}


def test_o_perfil_que_sai_da_pasta_sai_da_lista(pasta_cheia: pathlib.Path) -> None:
    assert len(perfil.lista()) == PERFIS
    (pasta_cheia / "perfil_05.json").unlink()
    nomes = [linha["nome"] for linha in perfil.lista()]
    assert len(nomes) == PERFIS - 1
    assert "Perfil 05" not in nomes
    assert (str(pasta_cheia), "perfil_05.json") not in perfil._DO_DISCO


def test_a_lista_devolve_linhas_novas_a_cada_chamada(pasta_cheia: pathlib.Path) -> None:
    primeira = perfil.lista()
    primeira[0]["nome"] = "alterado por quem chamou"
    assert perfil.lista()[0]["nome"] != "alterado por quem chamou"


def test_o_nome_que_so_se_acha_pelo_slug_e_depois_pelo_nome_cru(pasta_cheia: pathlib.Path) -> None:
    """O arquivo do slug vale até nascer o do nome, que é a primeira perna do loader."""
    assert perfil.arquivo("Perfil 03") == pasta_cheia / "perfil_03.json"
    direto = pasta_cheia / "Perfil 03.json"
    direto.write_text('{"name": "Perfil 03"}', encoding="utf-8")
    assert perfil.arquivo("Perfil 03") == direto
    direto.unlink()
    assert perfil.arquivo("Perfil 03") == pasta_cheia / "perfil_03.json"
