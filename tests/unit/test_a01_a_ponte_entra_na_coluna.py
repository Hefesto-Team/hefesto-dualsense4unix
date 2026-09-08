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
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: SEM GAMEPAD E SEM NATIVO — o desfecho *"nenhuma"*, que é o que a máquina dela
#: diria hoje. É o caso que a decisão dela cita textualmente.
SEM_PONTE: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}
#: O GAMEPAD DE PÉ COM CONTROLE NA MESA — o desfecho BOM (*"pelo Hefesto"*).
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


# ---------------------------------------------------------------------------
# 1. A CORREÇÃO DE FATO — duas das três órfãs já estavam na coluna
# ---------------------------------------------------------------------------
def test_a_pausa_e_o_cadeado_ja_eram_fontes_da_coluna() -> None:
    """As outras duas frases da D-10 não precisavam de trabalho nenhum.

    Se esta régua reprovar um dia, o fato mudou de novo e a D-10 volta a ter
    trabalho — que é exatamente a notícia que se quer ter.
    """
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


# ---------------------------------------------------------------------------
# 2. A PONTE ENTRA — e só quando é má notícia
# ---------------------------------------------------------------------------
def test_a_ponte_sem_jogo_vira_aviso() -> None:
    """*"nenhuma — nenhum jogo está recebendo controle do Hefesto"*.

    A MORDIDA: troque o `if ruim not in frase` por `if True` e a frase deixa de
    virar aviso, reprovando aqui.
    """
    achado = aba._aviso_da_ponte(SEM_PONTE)
    assert achado is not None, "a ponte sem jogo não virou aviso"
    assert achado["selo"] == aba.SELO_DA_PONTE
    assert "nenhuma" in achado["texto"]
    assert achado["fonte"] == "home_actions.texto_da_ponte"


def test_a_ponte_chega_a_COLUNA_e_nao_so_a_funcao() -> None:  # noqa: N802
    """A OUTRA METADE, e ela é a que faltava — medida na mordida de 04/09.

    A régua acima prova que `_aviso_da_ponte` sabe responder; ela **passa com o
    `fora.append(ponte)` arrancado de `_avisos`**, porque nunca olha a coluna.
    Uma régua assim daria verde sobre o estado exato que esta sprint veio curar:
    a frase existindo no produto e não chegando a tela nenhuma.

    A MORDIDA: apague o `fora.append(ponte)` de `_avisos` — esta reprova, e a
    de cima continua verde. É por isso que as duas existem.
    """
    ctx = Contexto(state=SEM_PONTE, mesa=[], conectados=[], estados={})
    fora = aba.coluna_de_atencao(ctx)
    assert aba.SELO_DA_PONTE in fora["aviso-selo"], (
        f"a ponte não chegou à coluna Atenção: {fora['aviso-selo']!r}")
    i = fora["aviso-selo"].index(aba.SELO_DA_PONTE)
    assert "nenhuma" in fora["aviso-texto"][i]
    # E ELA ENTRA NA CONTA: a coluna e o número ao lado falam do mesmo conjunto.
    assert fora["atencao-conta"] == painel.texto_da_conta(len(aba._avisos(ctx)))


def test_a_boa_noticia_da_ponte_nao_entra() -> None:
    """A coluna chama-se **Atenção** — a mesma disciplina dos `certo` do exame.

    A MORDIDA: troque o `if ruim not in frase: return None` por `if False:` e
    os dois desfechos bons passam a aparecer sob o cabeçalho laranja — que é o
    defeito fotografado em 02/09 com o selo `CERTO`.
    """
    assert aba._aviso_da_ponte(PONTE_BOA) is None, (
        "'pelo Hefesto' é boa notícia e entrou na coluna Atenção")
    assert aba._aviso_da_ponte(NATIVO) is None, (
        "'direto (Sony)' é boa notícia e entrou na coluna Atenção")


def test_sem_daemon_a_ponte_nao_afirma_nada() -> None:
    """*"não sei — o Hefesto está desligado"* não é aviso: é ausência de dado.

    Mesma guarda do `_estado_da_tela` e do `autoswitch_lock_text`: offline é
    "não sei", nunca "nenhuma".
    """
    assert aba._aviso_da_ponte({}) is None


def test_o_markup_do_pango_nao_chega_a_tela() -> None:
    """O piloto escreve `textContent`: um `<span foreground=…>` iria LITERAL.

    A MORDIDA: tire o `sem_markup(...)` e o texto do aviso passa a conter
    ``<span foreground="#ffb86c">``, reprovando aqui.
    """
    achado = aba._aviso_da_ponte(SEM_PONTE)
    assert achado is not None
    assert "<" not in achado["texto"] and ">" not in achado["texto"], (
        f"markup do Pango chegou ao texto da coluna: {achado['texto']!r}")
    assert not achado["texto"].startswith(home_actions.PONTE_PREFIXO), (
        "o prefixo ficou junto do selo: a linha diria 'PONTE  Ponte com o "
        f"jogo: …' — {achado['texto']!r}")


def test_se_a_cor_do_produto_sumir_a_regua_cala_em_vez_de_alarmar(
        monkeypatch: Any) -> None:
    """A guarda que impede um `"" in frase` de casar com TUDO.

    Sem ela, o dia em que `_COR_AVISO` mudar de nome encheria a coluna de boa
    notícia vestida de alerta — que é o defeito que o `_do_exame` já custou
    nesta aba, e o mais caro de diagnosticar, porque parece funcionar.

    A MORDIDA: apague o `if not ruim: return None` e este teste reprova com a
    boa notícia virando aviso.
    """
    monkeypatch.setattr(home_actions, "_COR_AVISO", "", raising=False)
    assert aba._aviso_da_ponte(SEM_PONTE) is None
    assert aba._aviso_da_ponte(PONTE_BOA) is None


def test_a_ponte_tem_lugar_na_escada_de_gravidade() -> None:
    """Um selo fora da escada cai para o fim da coluna, e some no `+N`.

    A MORDIDA: tire ``"PONTE"`` de `ORDEM_DA_GRAVIDADE` e a linha passa a
    disputar as vagas com os achados do exame — numa máquina com três avisos, a
    frase que responde *"por onde o jogo está recebendo o controle"* é a que
    fica de fora.
    """
    assert aba.SELO_DA_PONTE in aba.ORDEM_DA_GRAVIDADE
