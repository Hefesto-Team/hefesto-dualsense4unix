#!/usr/bin/env python3
"""A linha "Ponte com o jogo" — a órfã da D-10 que não tinha canal nenhum.

DECISÃO DELA — 04/09/2026, D-10: *"Todas na coluna Atenção."*

**CORREÇÃO DE FATO, e ela é o achado desta régua.** A D-10 nomeia TRÊS frases
órfãs da aba Jogar — a ponte, o cadeado *"não trocar de perfil sozinho"* e o
aviso de PAUSA. Medido na árvore de hoje, **duas já estavam na coluna** desde
03/09: `painel.AVISOS_DA_TELA` abre com `texto_da_pausa` e fecha com
`autoswitch_lock_text` e `texto_do_cadeado_cego`. A ponte era a única sem canal.

O QUE ESTA RÉGUA GUARDA, e é a decisão de projeto que ela mede: **quem diz se a
ponte é má notícia é o PRODUTO, pela cor que ele mesmo pinta.** `texto_da_ponte`
devolve markup do Pango com `_COR_OK` nos dois desfechos bons e `_COR_AVISO` nos
dois ruins. Reescrever aqui as quatro perguntas dela seria a segunda cópia de uma
regra que já tem dono — e a de cá envelheceria no primeiro desfecho novo.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.home_actions`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from pacotes import Contexto
from pacotes import a01_jogar as aba

SEM_PONTE: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}
PONTE_BOA: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}
#: O MODO NATIVO — também BOM (*"direto (Sony)"*): o jogo fala com o DualSense.
NATIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}


def test_a_pausa_e_o_cadeado_ja_eram_fontes_da_coluna() -> None:
    """As outras duas frases da D-10 não precisavam de trabalho nenhum."""
    nomes = {a.nome for a in painel.AVISOS_DA_TELA}
    assert "home_actions.texto_da_pausa" in nomes, (
        "a PAUSA saiu da coluna Atenção — ela era uma das três órfãs da D-10")
    assert "home_actions.autoswitch_lock_text" in nomes, (
        "o cadeado da troca automática saiu da coluna Atenção")
    assert "home_actions.texto_do_cadeado_cego" in nomes, (
        "o detector cego saiu da coluna Atenção")
    assert "home_actions.texto_da_ponte" not in nomes, (
        "a ponte entrou em `AVISOS_DA_TELA`: então ela passou a ter DOIS donos "
        "nesta coluna — o de lá e o `_aviso_da_ponte` daqui")


def test_a_ponte_sem_jogo_vira_aviso() -> None:
    """*"nenhuma — nenhum jogo está recebendo controle do Hefesto"*."""
    achado = aba._aviso_da_ponte(SEM_PONTE)
    assert achado is not None, "a ponte sem jogo não virou aviso"
    assert achado["selo"] == aba.SELO_DA_PONTE
    assert "nenhuma" in achado["texto"]
    assert achado["fonte"] == "home_actions.texto_da_ponte"


def test_a_ponte_chega_a_COLUNA_e_nao_so_a_funcao() -> None:  # noqa: N802
    """A OUTRA METADE, e ela é a que faltava — medida na mordida de 04/09."""
    ctx = Contexto(state=SEM_PONTE, mesa=[], conectados=[], estados={})
    fora = aba._avisos(ctx)
    selos = [a["selo"] for a in fora]
    assert aba.SELO_DA_PONTE in selos, (
        f"a ponte não chegou ao canal de avisos: {selos!r}")
    assert "nenhuma" in fora[selos.index(aba.SELO_DA_PONTE)]["texto"]


def test_a_ponte_nao_vira_linha_sem_assunto_na_09() -> None:
    """Na 09 a ponte virava «AVISO · Nenhuma» — a cabeça da frase, sem o assunto."""
    from pacotes import a09_sistema

    ctx = Contexto(state=SEM_PONTE, mesa=[], conectados=[], estados={})
    selos = [a["selo"] for a in aba.coluna_de_atencao(ctx)]
    assert aba.SELO_DA_PONTE not in selos, (
        f"a ponte foi levada à lista da aba Sistema: {selos!r}")
    na_tela = [a09_sistema.frase_curta_do_exame(str(linha["txt"]))
               for linha in a09_sistema._avisos_do_produto(ctx)]
    assert "Nenhuma" not in na_tela, (
        f"o exame da 09 mostra uma linha sem assunto: {na_tela!r}")


def test_a_boa_noticia_da_ponte_nao_entra() -> None:
    """A coluna chama-se **Atenção** — a mesma disciplina dos `certo` do exame."""
    assert aba._aviso_da_ponte(PONTE_BOA) is None, (
        "'pelo Hefesto' é boa notícia e entrou na coluna Atenção")
    assert aba._aviso_da_ponte(NATIVO) is None, (
        "'direto (Sony)' é boa notícia e entrou na coluna Atenção")


def test_sem_daemon_a_ponte_nao_afirma_nada() -> None:
    """*"não sei — o Hefesto está desligado"* não é aviso: é ausência de dado."""
    assert aba._aviso_da_ponte({}) is None


def test_o_markup_do_pango_nao_chega_a_tela() -> None:
    """O piloto escreve `textContent`: um `<span foreground=…>` iria LITERAL."""
    achado = aba._aviso_da_ponte(SEM_PONTE)
    assert achado is not None
    assert "<" not in achado["texto"] and ">" not in achado["texto"], (
        f"markup do Pango chegou ao texto da coluna: {achado['texto']!r}")
    assert not achado["texto"].startswith(home_actions.PONTE_PREFIXO), (
        "o prefixo ficou junto do selo: a linha diria 'PONTE  Ponte com o "
        f"jogo: …' — {achado['texto']!r}")


def test_se_a_cor_do_produto_sumir_a_regua_cala_em_vez_de_alarmar(
        monkeypatch: Any) -> None:
    """A guarda que impede um `"" in frase` de casar com TUDO."""
    monkeypatch.setattr(home_actions, "_COR_AVISO", "", raising=False)
    assert aba._aviso_da_ponte(SEM_PONTE) is None
    assert aba._aviso_da_ponte(PONTE_BOA) is None


def test_a_ponte_tem_lugar_na_escada_de_gravidade() -> None:
    """Um selo fora da escada cai para o fim da coluna, e some no `+N`."""
    assert aba.SELO_DA_PONTE in aba.ORDEM_DA_GRAVIDADE
