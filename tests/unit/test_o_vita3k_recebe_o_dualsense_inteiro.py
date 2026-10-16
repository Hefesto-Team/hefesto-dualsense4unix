#!/usr/bin/env python3
"""O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01 — o perfil do Vita3K entra pela janela dele.

O cartão que o produto acha pelo `.desktop` só sabe o nome do arquivo. Sem a classe de janela
na linha «todos os jogos», o perfil criado pela aba nunca casa o Vita3K aberto.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.profiles.schema import MatchCriteria


@pytest.fixture
def lar(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar de mentira: nada do `~/.config` dela é lido."""
    for nome, sub in (("HOME", ""), ("XDG_DATA_HOME", "share"), ("XDG_CONFIG_HOME", "cfg"),
                      ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "st"),
                      ("XDG_DATA_DIRS", "vazio")):
        monkeypatch.setenv(nome, str(tmp_path / sub) if sub else str(tmp_path))
    a07._ESCOLHA.limpar()
    a07._ESCOLHA.modo = desenho.EXCLUIR
    return tmp_path


def _achados(monkeypatch: pytest.MonkeyPatch,
             achados: dict[str, str]) -> tuple[desenho.SemCenso, ...]:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: achados)
    return a07._achados_por_conteudo()


def _janelas_da_linha(cartao: desenho.SemCenso) -> list[str]:
    _jogos, janelas, _emu = a07._jogos_para_escolher(cartao.chave, cartao.nome, None)
    return [j for classes in janelas.values() for j in classes]


def test_o_vita3k_achado_pelo_desktop_leva_a_classe_da_janela(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A linha «todos os jogos» do Vita3K casa a janela dele, no AppImage e no AUR."""
    (cartao,) = _achados(monkeypatch, {"org.vita3k.vita3k": "Vita3K"})
    assert cartao.atalhos == ("org.vita3k.vita3k",)
    assert cartao.comandos == ()
    criterio = MatchCriteria(window_class=_janelas_da_linha(cartao))
    assert criterio.matches({"wm_class": "Vita3K"})
    assert criterio.matches({"wm_class": "vita3k"})


def test_a_linha_arrancada_deixa_o_perfil_sem_janela(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: sem a tabela, só o nome do arquivo sobra e a janela real não casa."""
    monkeypatch.setattr(a07, "_JANELAS_DO_EMULADOR_ACHADO", {})
    (cartao,) = _achados(monkeypatch, {"org.vita3k.vita3k": "Vita3K"})
    criterio = MatchCriteria(window_class=_janelas_da_linha(cartao))
    assert not criterio.matches({"wm_class": "Vita3K"})


def test_a_chave_e_a_do_cartao_e_nao_o_nome_do_arquivo() -> None:
    """MORDIDA: a tabela errada pelo `stem` (com ponto) nunca seria achada."""
    assert "org-vita3k-vita3k" in a07._JANELAS_DO_EMULADOR_ACHADO
    assert all("." not in chave and chave == chave.lower()
               for chave in a07._JANELAS_DO_EMULADOR_ACHADO)


def test_lancador_desconhecido_nao_ganha_janela_inventada(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem medida não há classe: o Bottles segue só com o nome do arquivo."""
    (cartao,) = _achados(monkeypatch, {"com.usebottles.bottles": "Bottles"})
    assert cartao.janelas == ()
    assert cartao.atalhos == ("com.usebottles.bottles",)
