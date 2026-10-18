#!/usr/bin/env python3
"""O-SHADPS4-QUE-JA-MORA-AQUI-01 — o perfil do shadPS4 entra pela janela dele, nas duas chaves.

O cartão achado pelo `.desktop` só sabe o nome do arquivo. O shadPS4 do projeto dela sobe com
`SDL_APP_ID=net.shadps4.shadPS4`; o AppImage oficial aberto direto se anuncia por `shadps4`. Sem a
classe na linha «todos os jogos», o perfil criado pela aba nunca casa o emulador aberto.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a07_lancadores`, que carrega o GTK")

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.profiles.schema import MatchCriteria

_OFICIAL = "net.shadps4.shadPS4"
_COSMIC = "io.github.vitoriamaria.shadps4-cosmic"


@pytest.fixture
def lar(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar de mentira: nada do `~/.config` dela é lido."""
    for nome, sub in (("HOME", ""), ("XDG_DATA_HOME", "share"), ("XDG_CONFIG_HOME", "cfg"),
                      ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "st"),
                      ("XDG_DATA_DIRS", "vazio")):
        monkeypatch.setenv(nome, str(tmp_path / sub) if sub else str(tmp_path))
    a07._ESCOLHA.limpar()
    a07._ESCOLHA.modo = desenho.CRIAR_PERFIL
    return tmp_path


def _achados(monkeypatch: pytest.MonkeyPatch,
             achados: dict[str, str]) -> tuple[desenho.SemCenso, ...]:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: achados)
    return a07._achados_por_conteudo()


def _criterio(cartao: desenho.SemCenso) -> MatchCriteria:
    _jogos, janelas, _emu = a07._jogos_para_escolher(cartao.chave, cartao.nome, None)
    return MatchCriteria(window_class=[j for classes in janelas.values() for j in classes])


def test_os_dois_cartoes_do_shadps4_casam_a_janela_dele(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Oficial e do projeto dela: a linha «todos os jogos» casa `shadps4` e o app_id do run.sh."""
    oficial, cosmic = _achados(
        monkeypatch, {_OFICIAL: "shadPS4", _COSMIC: "shadPS4 Cosmic"})
    assert {oficial.chave, cosmic.chave} == {"net-shadps4-shadps4",
                                             "io-github-vitoriamaria-shadps4-cosmic"}
    for cartao in (oficial, cosmic):
        criterio = _criterio(cartao)
        assert criterio.matches({"wm_class": "shadps4"}), cartao.chave
        assert criterio.matches({"wm_class": _OFICIAL}), cartao.chave


def test_o_cartao_do_projeto_dela_casa_o_app_id_do_run_sh(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `SDL_APP_ID` do run.sh vira a janela; a comparação ignora a caixa."""
    (cartao,) = _achados(monkeypatch, {_COSMIC: "shadPS4 Cosmic"})
    criterio = _criterio(cartao)
    assert criterio.matches({"wm_class": "net.shadps4.shadPS4"})
    assert criterio.matches({"wm_class": "NET.SHADPS4.SHADPS4"})


def test_o_launcher_qt_nao_casa(lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # D-1610-O-LAUNCHER-QT-DO-SHADPS4-NAO-PUXA-O-PERFIL
    """FOCO-ERRANTE-01: o launcher Qt fica vivo durante outro jogo e não pode puxar o perfil."""
    oficial, cosmic = _achados(
        monkeypatch, {_OFICIAL: "shadPS4", _COSMIC: "shadPS4 Cosmic"})
    for cartao in (oficial, cosmic):
        assert not _criterio(cartao).matches({"wm_class": "shadPS4QtLauncher"}), cartao.chave
    tudo = [j for chave in ("net-shadps4-shadps4", "io-github-vitoriamaria-shadps4-cosmic")
            for j in a07._JANELAS_DO_EMULADOR_ACHADO[chave]]
    assert not any("launcher" in j.lower() for j in tudo)


def test_a_linha_arrancada_deixa_o_shadps4_sem_janela(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: sem a tabela, só o nome do arquivo sobra e a janela real não casa."""
    monkeypatch.setattr(a07, "_JANELAS_DO_EMULADOR_ACHADO", {})
    oficial, cosmic = _achados(
        monkeypatch, {_OFICIAL: "shadPS4", _COSMIC: "shadPS4 Cosmic"})
    for cartao in (oficial, cosmic):
        assert not _criterio(cartao).matches({"wm_class": "shadps4"}), cartao.chave


def test_so_a_chave_do_projeto_dela_deixa_o_oficial_de_fora(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: quem usa o shadPS4 sem o projeto dela não pode ficar de fora."""
    so_cosmic = {"io-github-vitoriamaria-shadps4-cosmic":
                 a07._JANELAS_DO_EMULADOR_ACHADO["io-github-vitoriamaria-shadps4-cosmic"]}
    monkeypatch.setattr(a07, "_JANELAS_DO_EMULADOR_ACHADO", so_cosmic)
    (oficial,) = _achados(monkeypatch, {_OFICIAL: "shadPS4"})
    assert not _criterio(oficial).matches({"wm_class": "shadps4"})


def test_a_tabela_cobre_as_duas_chaves_com_a_forma_do_cartao() -> None:
    """A chave é a do cartão (minúscula, sem ponto), e as duas do shadPS4 existem."""
    tabela = a07._JANELAS_DO_EMULADOR_ACHADO
    for chave in ("net-shadps4-shadps4", "io-github-vitoriamaria-shadps4-cosmic"):
        assert chave in tabela, chave
        assert "." not in chave and chave == chave.lower()
    assert "shadps4" in {j.casefold() for j in tabela["net-shadps4-shadps4"]}
    assert {"net.shadps4.shadps4", "shadps4"} <= {
        j.casefold() for j in tabela["io-github-vitoriamaria-shadps4-cosmic"]}
