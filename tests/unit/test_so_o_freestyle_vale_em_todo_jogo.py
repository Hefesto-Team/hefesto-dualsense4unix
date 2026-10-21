#!/usr/bin/env python3
"""SO-O-FREESTYLE-VALE-EM-TODO-JOGO-01 — a tela diz o que o gerente faz com o `any`.

Desde 01/10 o `match any` não entra em seleção automática nenhuma, e o Freestyle
vale pelo botão. A escolha de 08/10/2026 (`ESCOLHAS.md`): na coluna «Funciona em»,
«Só quando eu escolher»; a cauda «vale em todo jogo…» sai da dica do Salvar e mora
no balão do Aplicar, só com o Modo Freestyle ligado; «Qualquer jogo» sai da oferta.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest


from hefesto_dualsense4unix.app.actions.profiles_actions import (
    LABEL_SO_MANUAL,
    rotulo_quando_usar,
)
from hefesto_dualsense4unix.interface import onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import simple_match as sm
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
CAUDA_DO_MANUAL = "vale quando você escolher este perfil."


def _o_disco_cru(monkeypatch: pytest.MonkeyPatch, **por_nome: dict[str, Any]) -> None:
    """O `match` que o `_tipo_do_perfil` lê de cada nome, sem disco de verdade."""
    monkeypatch.setattr(_perfil, "ativo", lambda nome: por_nome.get(nome, {}))


def test_a_dica_do_salvar_do_freestyle_nao_tem_a_cauda(monkeypatch) -> None:
    """O Freestyle é `any` no disco, e a dica do Salvar dele não promete jogo.

    A MORDIDA: tire do `_tipo_do_perfil` a pergunta pela identidade
    (`e_o_freestyle`) e o Freestyle volta a ser lido pelo `match`: ganha a cauda
    do manual, que é falsa para ele.
    """
    _o_disco_cru(monkeypatch, Freestyle={"match": {"type": "any"}})
    assert pacotes._dica_do_salvar("Freestyle") == (
        "Grava no perfil Freestyle. É onde a mudança vai cair.")


def test_o_any_que_nao_e_o_freestyle_e_o_manual(monkeypatch) -> None:
    """Outro `any`: a cauda e o rótulo do manual, porque ele só vale escolhido."""
    _o_disco_cru(monkeypatch, Universal={"match": {"type": "any"}})
    assert pacotes._dica_do_salvar("Universal").endswith(CAUDA_DO_MANUAL)
    universal = Profile(name="Universal", match=MatchAny(), priority=0)
    assert rotulo_quando_usar(universal, [universal]) == LABEL_SO_MANUAL
    assert LABEL_SO_MANUAL == sm.ROTULO_SO_QUANDO_ESCOLHER == "Só quando eu escolher"


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: alvo)
    return alvo


@pytest.mark.parametrize("janela", ["firefox", "steam_app_1245620"])
def test_a_frase_segue_o_gerente(disco, monkeypatch, janela) -> None:
    """O gerente de verdade, num disco de mentira: o `any` entra sozinho?

    A frase da tela é a do manual SE E SÓ SE ele não entra. A MORDIDA: devolva o
    `any` à seleção automática (`select_for_window_ex` sem o filtro do
    `e_catch_all`) e a régua passa a exigir outra frase, que a tela não diz.
    """
    loader.save_profile(Profile(name="Universal", match=MatchAny(), priority=0))
    gerente = ProfileManager(controller=FakeController())
    escolhido, _motivo = gerente.select_for_window_ex({"wm_class": janela})
    entra_sozinho = escolhido is not None and escolhido.name == "Universal"

    _o_disco_cru(monkeypatch, Universal={"match": {"type": "any"}})
    diz_o_manual = pacotes._dica_do_salvar("Universal").endswith(CAUDA_DO_MANUAL)
    assert diz_o_manual is not entra_sozinho


@pytest.mark.parametrize("ligado", [True, False, None], ids=["aceso", "apagado", "sem-resposta"])
def test_o_balao_do_aplicar_so_fala_do_freestyle_aceso(ligado) -> None:
    """Aceso, o Aplicar diz que vale em todo jogo; apagado ou mudo, a dica de sempre.

    A MORDIDA: devolva a cauda ao Salvar e tire-a do Aplicar, e o aceso reprova.
    """
    ctx = Contexto(state={"freestyle_ligado": ligado}, mesa=[], conectados=[], estados={})
    dica = pacotes.topo(ctx)["rodape.aplicar"]
    assert dica.endswith(pacotes.CAUDA_DO_FREESTYLE) is (ligado is True), dica
    assert dica.startswith(pacotes.DICA_DO_APLICAR)


def test_o_aplicar_de_sempre_e_o_do_rodape_congelado() -> None:
    """A dica de sempre do pacote é, letra por letra, a que o `fim.html` congela."""
    fim = (onde.AQUI / "fim.html").read_text(encoding="utf-8")
    botao = re.search(r'<button class="r-aplicar"([^>]*)>', fim, re.S)
    assert botao, "o Aplicar sumiu do rodapé"
    assert f'title="{pacotes.DICA_DO_APLICAR}"' in botao.group(1)


def test_o_balao_do_aplicar_tem_onde_cair_nas_paginas() -> None:
    """Cada dica do rodapé que o `topo` emite tem um botão com aquele endereço.

    O `rodape.aplicar` nasceu em 08/10 (1d1e65a5d) sem `data-campo` no Aplicar:
    a cauda do Freestyle era calculada a cada tique e não chegava a tela nenhuma.
    A MORDIDA: tire o `data-campo="rodape.aplicar"` do `fim.html` e esta reprova.
    """
    ctx = Contexto(state={"freestyle_ligado": True}, mesa=[], conectados=[], estados={})
    chaves = [k for k in pacotes.topo(ctx) if k.startswith("rodape.")]
    assert "rodape.aplicar" in chaves
    fim = (onde.AQUI / "fim.html").read_text(encoding="utf-8")
    paginas = [p for p in onde.paginas(publicado=True)
               if 'class="r-aplicar"' in p.read_text(encoding="utf-8")]
    assert paginas, "nenhuma página publicada tem o rodapé"
    for chave in chaves:
        endereco = (f'data-campo="{chave}"\n'
                    '            data-hef-alvo="atributo" data-hef-atributo="title"')
        assert endereco in fim, f"`{chave}` sai do `topo` e o `fim.html` não tem onde pô-la"
        sem = [p.name for p in paginas if endereco not in p.read_text(encoding="utf-8")]
        assert not sem, f"`{chave}` sem endereço nas páginas publicadas: {sem}"


FRASES_DA_DISPUTA = (
    "Sempre — 4 disputam",
    "Sempre — quando nenhum casa",
    "Todos — quando nenhum casa",
    "em todo jogo sem perfil próprio",
    "e só o perfil próprio de um jogo entra por cima",
    "e só contra janela comum: o perfil próprio de um jogo entra por cima",
    "«Funciona em» «Qualquer jogo»",
)


def test_nenhum_texto_vivo_descreve_a_disputa() -> None:
    """Os geradores, os pacotes e o O-COMO-DAS-21 não dizem mais o «quando nenhum casa».

    A MORDIDA: devolva a linha «Sempre — 4 disputam» ao `aba10.PERFIS` e reprova.
    """
    alvos = [RAIZ / "docs/method/2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md",
             *sorted((RAIZ / "src/hefesto_dualsense4unix").rglob("*.py"))]
    achados = [f"{a.relative_to(RAIZ)}: {frase}"
               for a in alvos for frase in FRASES_DA_DISPUTA
               if frase in a.read_text(encoding="utf-8")]
    assert achados == []
