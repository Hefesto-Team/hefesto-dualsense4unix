"""Verificador semântico dos perfis (PERFIL-NASCE-CERTO-01/E4).

A fixture central (`perfis_da_corrupcao`) é o RETRATO do que estava no disco
dela em 04/08/2026, com nomes e MACs mascarados (faixa da casa,
``AA:BB:CC:00:00:xx``): um catch-all de prioridade alta vencendo o perfil do
jogo, o perfil do jogo com o `match` trocado por ``any``, prioridades
empatadas, um número fora da faixa que a janela oferece e quatro catch-all no
mesmo diretório.

Cada teste diz, na docstring, o que reprova quando a regra correspondente é
arrancada de `profiles/sanidade.py`.
"""
from __future__ import annotations

from collections.abc import Sequence

import pytest

from hefesto_dualsense4unix.profiles import sanidade
from hefesto_dualsense4unix.profiles.sanidade import Achado, verificar_perfis
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
    ProfileModeConfig,
)


def _perfil(
    nome: str,
    *,
    match: Match | None = None,
    priority: int = 0,
    modo: str | None = None,
    suprime: bool = False,
    controles: dict[str, ControllerOverrides] | None = None,
) -> Profile:
    return Profile(
        name=nome,
        match=match if match is not None else MatchCriteria(window_class=[nome]),
        priority=priority,
        leds=LedsConfig(lightbar=(0, 0, 0)),
        mode=ProfileModeConfig(kind=modo) if modo is not None else None,
        suppress_desktop_emulation=suprime,
        controllers=controles,
    )


def _regras(achados: Sequence[Achado]) -> set[str]:
    return {a.regra for a in achados}


def _de(achados: Sequence[Achado], regra: str) -> list[Achado]:
    return [a for a in achados if a.regra == regra]


@pytest.fixture
def perfis_da_corrupcao() -> list[Profile]:
    """O arranjo medido no disco dela, com nomes/MACs mascarados.

    Um perfil é acréscimo declarado: `editado_na_mao` (prioridade 250). No
    disco dela o maior número era 191 — alcançável pelo slider, e por isso
    coberto por OUTRA regra. O 250 existe aqui para exercitar a faixa, e
    representa o caso que o slider não explica: JSON editado à mão.
    """
    return [
        _perfil(
            "editado_na_mao",
            match=MatchCriteria(window_class=["editor"]),
            priority=250,
        ),
        # O catch-all de desktop que subiu e passou a vencer tudo.
        _perfil("desktop_dela", match=MatchAny(), priority=100),
        # O perfil do JOGO que perdeu o `match` por dentro da janela.
        _perfil("pragmata", match=MatchAny(), priority=191, modo="gamepad"),
        # Catch-all legítimo, no fundo da escala: NÃO pode virar achado.
        _perfil("fallback", match=MatchAny(), priority=0),
        # Mais um catch-all sem alvo, do tempo dos testes dela.
        _perfil("meu_perfil", match=MatchAny(), priority=50),
        # Perfis com alvo de verdade, empatados entre si.
        _perfil(
            "sackboy",
            match=MatchCriteria(window_class=["sackboy"]),
            priority=50,
            controles={"AA:BB:CC:00:00:02": ControllerOverrides()},
        ),
        _perfil("navegacao", match=MatchCriteria(process_name=["firefox"]), priority=50),
        # Só-manual declarado: nunca disputa, nunca vira achado.
        _perfil("festa", match=MatchManual(), priority=50),
    ]


# ---------------------------------------------------------------------------
# O retrato inteiro
# ---------------------------------------------------------------------------


def test_o_disco_dela_produz_exatamente_estes_achados(
    perfis_da_corrupcao: list[Profile],
) -> None:
    """As cinco regras disparam no arranjo real, e nenhuma outra.

    MORDIDA: arrancar QUALQUER das cinco funções de `sanidade.REGRAS` faz esta
    comparação de conjuntos reprovar nomeando a regra que sumiu.
    """
    achados = verificar_perfis(perfis_da_corrupcao)
    assert _regras(achados) == {
        "catch_all_vence_especifico",
        "catch_all_com_cara_de_jogo",
        "prioridades_empatadas",
        "prioridade_fora_da_faixa",
        "catch_all_demais",
    }


def test_todo_achado_diz_o_que_fazer(perfis_da_corrupcao: list[Profile]) -> None:
    """Achado sem cura é alarme que se aprende a ignorar.

    MORDIDA: esvaziar o `cura=` de qualquer `Achado` reprova aqui.
    """
    for achado in verificar_perfis(perfis_da_corrupcao):
        assert achado.cura.strip(), f"{achado.regra} não diz o que fazer"
        assert achado.mensagem.strip()
        assert achado.gravidade in {"erro", "aviso"}
        assert achado.perfis, f"{achado.regra} não nomeia perfil nenhum"
        assert achado.cura in achado.linha()


def test_disco_saudavel_fica_calado() -> None:
    """Arranjo coerente = zero achado (o silêncio é o que dá crédito ao alarme).

    MORDIDA: afrouxar a dispensa do `fallback` (ou contá-lo entre os catch-all)
    faz aparecer achado num diretório que está certo.
    """
    perfis = [
        _perfil("fallback", match=MatchAny(), priority=0),
        _perfil("pragmata", match=MatchCriteria(window_class=["pragmata"]), priority=80),
        _perfil("sackboy", match=MatchCriteria(window_class=["sackboy"]), priority=70),
        _perfil("festa", match=MatchManual(), priority=60),
    ]
    assert verificar_perfis(perfis) == []


# ---------------------------------------------------------------------------
# Regra 1 — catch-all vencendo perfil específico (a que abriu a sprint)
# ---------------------------------------------------------------------------


def test_catch_all_acima_de_especifico_e_erro() -> None:
    """`vitoria` (any/100) vencendo o perfil do jogo é a armadilha original."""
    achados = _de(
        verificar_perfis(
            [
                _perfil("desktop_dela", match=MatchAny(), priority=100),
                _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=80),
            ]
        ),
        "catch_all_vence_especifico",
    )
    assert len(achados) == 1
    assert achados[0].gravidade == "erro"
    assert "desktop_dela" in achados[0].mensagem
    assert "pragmata (80)" in achados[0].mensagem


def test_empate_entre_catch_all_e_especifico_tambem_conta() -> None:
    """No empate quem vence é a ordem de leitura — 'às vezes certo' é pior."""
    achados = verificar_perfis(
        [
            _perfil("desktop_dela", match=MatchAny(), priority=80),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=80),
        ]
    )
    assert "catch_all_vence_especifico" in _regras(achados)


def test_catch_all_abaixo_do_especifico_nao_e_achado() -> None:
    """O arranjo CERTO (catch-all embaixo) não pode virar alarme."""
    achados = verificar_perfis(
        [
            _perfil("desktop_dela", match=MatchAny(), priority=10),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=80),
        ]
    )
    assert "catch_all_vence_especifico" not in _regras(achados)


def test_criteria_vazio_conta_como_catch_all() -> None:
    """`MatchCriteria` sem nenhum campo é catch-all pelo predicado do schema."""
    achados = verificar_perfis(
        [
            _perfil("coop_local", match=MatchCriteria(), priority=90),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=80),
        ]
    )
    assert "catch_all_vence_especifico" in _regras(achados)


# ---------------------------------------------------------------------------
# A dispensa nomeada do `fallback`
# ---------------------------------------------------------------------------


def test_fallback_no_fundo_da_escala_tem_dispensa() -> None:
    """`fallback` em 0 é catch-all LEGÍTIMO — acusá-lo seria alarme perpétuo.

    MORDIDA: apagar `CATCH_ALL_LEGITIMOS` (ou a checagem `_tem_dispensa`) faz
    o arranjo recomendado pelo próprio projeto virar achado.
    """
    achados = verificar_perfis(
        [
            _perfil("fallback", match=MatchAny(), priority=0),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=0),
        ]
    )
    assert "catch_all_vence_especifico" not in _regras(achados)
    assert "catch_all_com_cara_de_jogo" not in _regras(achados)


def test_fallback_que_sobe_perde_a_dispensa() -> None:
    """Um "fallback" em 100 não é fundo de escala — é competidor.

    É a forma exata da corrupção medida (prioridades subindo sozinhas), e a
    dispensa não pode servir de esconderijo para ela.
    """
    achados = verificar_perfis(
        [
            _perfil("fallback", match=MatchAny(), priority=100),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=80),
        ]
    )
    assert "catch_all_vence_especifico" in _regras(achados)


def test_dispensa_e_por_slug_nao_por_grafia() -> None:
    """"Fallback" e "fallback" são o mesmo perfil (mesmo arquivo)."""
    achados = verificar_perfis(
        [
            _perfil("Fallback", match=MatchAny(), priority=0),
            _perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=0),
        ]
    )
    assert "catch_all_vence_especifico" not in _regras(achados)


# ---------------------------------------------------------------------------
# Regra 2 — nome de jogo com `match.type == "any"`
# ---------------------------------------------------------------------------


def test_perfil_de_jogo_declarado_com_match_any() -> None:
    """Pede modo gamepad e casa com tudo = perdeu a regra dele.

    MORDIDA: arrancar `_catch_all_com_cara_de_jogo` some com este achado.
    """
    achados = _de(
        verificar_perfis([_perfil("pragmata", match=MatchAny(), priority=0, modo="gamepad")]),
        "catch_all_com_cara_de_jogo",
    )
    assert len(achados) == 1
    assert "modo de jogo" in achados[0].mensagem
    assert "manual" in achados[0].cura


def test_supressao_de_desktop_tambem_denuncia() -> None:
    """Suprimir a emulação de desktop é declaração de perfil de jogo."""
    achados = verificar_perfis(
        [_perfil("qualquer_coisa", match=MatchAny(), priority=0, suprime=True)]
    )
    assert "catch_all_com_cara_de_jogo" in _regras(achados)


def test_nome_generico_com_match_any_fica_calado() -> None:
    """"desktop", "navegacao", "geral" — nome que diz "vale para tudo"."""
    perfis = [
        _perfil(nome, match=MatchAny(), priority=40)
        for nome in ("desktop", "navegacao", "geral", "meu_perfil")
    ]
    assert "catch_all_com_cara_de_jogo" not in _regras(verificar_perfis(perfis))


def test_nome_proprio_com_match_any_levanta_aviso() -> None:
    """`pragmata` sem alvo é o retrato do perfil que perdeu a regra."""
    achados = _de(
        verificar_perfis([_perfil("pragmata", match=MatchAny(), priority=100)]),
        "catch_all_com_cara_de_jogo",
    )
    assert len(achados) == 1
    assert achados[0].gravidade == "aviso"
    assert "prioridade 0" in achados[0].cura


def test_catch_all_de_nome_proprio_no_piso_nao_e_nagueado() -> None:
    """Todo alarme precisa ter um jeito de calar seguindo o conselho dele.

    Um catch-all parado na prioridade 0 se comporta como fundo de escala
    qualquer que seja o nome — não tira a vez de ninguém. Sem esta folga, o
    perfil de desktop com nome próprio (o caso DELA) levaria um aviso perpétuo
    que nenhuma ação apagaria, e o alarme inteiro perderia o crédito.

    MORDIDA: tirar o `p.priority > PRIORIDADE_DE_FUNDO` do sinal de nome faz
    este teste reprovar.
    """
    achados = verificar_perfis([_perfil("nome_dela", match=MatchAny(), priority=0)])
    assert achados == []


def test_perfil_de_jogo_declarado_nao_ganha_a_folga_do_piso() -> None:
    """Modo de jogo casando com TUDO é errado mesmo na prioridade 0.

    Ele empurraria o modo gamepad no desktop toda vez que nenhuma regra
    casasse — o defeito não depende do número.
    """
    achados = verificar_perfis(
        [_perfil("nome_dela", match=MatchAny(), priority=0, modo="gamepad")]
    )
    assert "catch_all_com_cara_de_jogo" in _regras(achados)


def test_perfil_manual_de_jogo_nao_e_acusado() -> None:
    """Quem DECLARA `manual` disse o que queria — não há acidente a apontar."""
    achados = verificar_perfis(
        [_perfil("pragmata", match=MatchManual(), priority=0, modo="gamepad")]
    )
    assert achados == []


# ---------------------------------------------------------------------------
# Regra 3 — prioridades empatadas
# ---------------------------------------------------------------------------


def test_empate_entre_especificos_e_achado() -> None:
    """MORDIDA: arrancar `_prioridades_empatadas` some com este achado."""
    achados = _de(
        verificar_perfis(
            [
                _perfil("sackboy", match=MatchCriteria(window_class=["s"]), priority=50),
                _perfil("navegacao", match=MatchCriteria(process_name=["f"]), priority=50),
            ]
        ),
        "prioridades_empatadas",
    )
    assert len(achados) == 1
    assert achados[0].perfis == ("navegacao", "sackboy")
    assert "50" in achados[0].mensagem


def test_empate_com_perfil_manual_nao_conta() -> None:
    """Perfil só-manual nunca é candidato — empatar com ele não decide nada."""
    achados = verificar_perfis(
        [
            _perfil("sackboy", match=MatchCriteria(window_class=["s"]), priority=50),
            _perfil("festa", match=MatchManual(), priority=50),
        ]
    )
    assert "prioridades_empatadas" not in _regras(achados)


# ---------------------------------------------------------------------------
# Regra 4 — prioridade fora da faixa da janela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prioridade", [-1, 201, 1000])
def test_prioridade_fora_da_faixa_e_erro(prioridade: int) -> None:
    """0-200 é o que o controle da janela oferece; fora dela veio de outro lugar.

    MORDIDA: arrancar `_prioridade_fora_da_faixa` some com este achado.
    """
    achados = _de(
        verificar_perfis(
            [_perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=prioridade)]
        ),
        "prioridade_fora_da_faixa",
    )
    assert len(achados) == 1
    assert achados[0].gravidade == "erro"
    assert "historico" in achados[0].cura  # (noqa-acento): nome de subcomando


@pytest.mark.parametrize("prioridade", [0, 100, 191, 200])
def test_prioridade_dentro_da_faixa_passa(prioridade: int) -> None:
    """191 é suspeito, mas é alcançável pelo slider — outra regra cuida dele."""
    achados = verificar_perfis(
        [_perfil("pragmata", match=MatchCriteria(window_class=["p"]), priority=prioridade)]
    )
    assert "prioridade_fora_da_faixa" not in _regras(achados)


# ---------------------------------------------------------------------------
# Regra 5 — catch-all demais
# ---------------------------------------------------------------------------


def test_muitos_catch_all_viram_achado() -> None:
    """MORDIDA: arrancar `_catch_all_demais` some com este achado."""
    perfis = [
        _perfil("fallback", match=MatchAny(), priority=0),
        _perfil("desktop_dela", match=MatchAny(), priority=1),
        _perfil("meu_perfil", match=MatchAny(), priority=2),
        _perfil("pragmata", match=MatchAny(), priority=3),
    ]
    achados = _de(verificar_perfis(perfis), "catch_all_demais")
    assert len(achados) == 1
    # O `fallback` dispensado NÃO entra na conta.
    assert set(achados[0].perfis) == {"desktop_dela", "meu_perfil", "pragmata"}


def test_um_catch_all_alem_do_fallback_e_tolerado() -> None:
    """O perfil de desktop de quem não quer regra nenhuma é legítimo."""
    perfis = [
        _perfil("fallback", match=MatchAny(), priority=0),
        _perfil("desktop", match=MatchAny(), priority=1),
    ]
    assert "catch_all_demais" not in _regras(verificar_perfis(perfis))


# ---------------------------------------------------------------------------
# Formatação para o doctor
# ---------------------------------------------------------------------------


def test_relatorio_marca_erro_e_aviso_com_tags_diferentes(
    perfis_da_corrupcao: list[Profile],
) -> None:
    linhas = sanidade.linhas_de_relatorio(verificar_perfis(perfis_da_corrupcao))
    tags = {tag for tag, _ in linhas}
    assert "[FAIL]" in tags
    assert "[WARN]" in tags


def test_relatorio_de_disco_saudavel_diz_ok() -> None:
    linhas = sanidade.linhas_de_relatorio([], total_perfis=7)
    assert linhas == [("[ OK ]", "perfis coerentes entre si (7 no disco)")]
