"""A-REGRA-QUE-A-TELA-NAO-MOSTRA-01 — o editor afirmava uma regra que não era a regra.

A FOTO DELA, 10/08/2026 às 03:57
================================
O editor de perfil, no modo simples, mostrava o perfil "Pragmata" assim::

    Aplica a: [Jogo da Steam]      Nome do jogo: 3357650
    [x] Esconder o controle físico neste jogo

E no arquivo estava, invisível::

    "process_name": ["PRAGMATA.exe"]

O `MatchCriteria.matches` é **AND**, então o campo invisível era o que decidia. O
perfil não entrava sozinho — medido **seis vezes entre 03:54 e 03:56**, com ela
jogando, cada uma um
``profile_select_catch_all_sem_autoridade_em_jogo candidatos=['fallback']
wm_class=steam_app_3357650``. O que ficava valendo era o perfil ANTERIOR: o
"Navegação", que casa com a janela do `steam` — e é o que a foto da aba Status
dela mostra, "Perfil ativo: Navegação", com o jogo aberto.

Nas palavras dela: *"na hora do jogo ele ou reseta pro controlar nativamente ou
não carrega o perfil ou não aplica nada do que eu fiz"*.

O QUE **NÃO** É O DEFEITO
=========================
Preservar o campo invisível ao salvar continua **certo**, e é decisão medida
(ESCONDER-EM-VEZ-DE-SAIR-01): salvar pela janela não pode apagar o que a tela não
mostra. Este arquivo não revoga aquilo — há teste abaixo que o protege.

O defeito era o **silêncio em volta**: a tela preservava e não contava.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    exigencia_invisivel,
    from_simple_choice,
)

#: O critério do perfil dela, byte a byte.
PRAGMATA = MatchCriteria(
    window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]
)


def test_o_caso_dela_e_declarado_com_o_campo_e_o_valor() -> None:
    """A cura. Morde ao fazer `exigencia_invisivel` devolver "" sempre.

    Sem isto a tela afirma "Jogo da Steam · 3357650" e cala sobre o campo que
    impede o perfil de entrar — que é o estado do produto até 10/08/2026.
    """
    texto = exigencia_invisivel(PRAGMATA)
    assert "nome do processo" in texto, "o rótulo tem de ser o do editor avançado"
    assert '"PRAGMATA.exe"' in texto, "o valor exato, para ela reconhecer"
    assert "Modo avançado" in texto, "e onde mexer, senão o aviso é beco sem saída"


def test_a_frase_nao_manda_apagar_nada() -> None:
    """Quem escreveu o critério foi ela; a decisão de mudá-lo é dela.

    A mesma regra da frase do PERFIL-MUDO-01: factual, nunca prescritiva, e sem
    afirmar mecanismo que o Hefesto não mediu (o que o Proton faz com o
    `/proc/PID/exe` segue SEM PROVA neste projeto).
    """
    texto = exigencia_invisivel(PRAGMATA).lower()
    for proibido in ("apague", "remova", "errado", "incorreto", "proton", "wine"):
        assert proibido not in texto


def test_sem_campo_invisivel_a_linha_nao_existe() -> None:
    """O caso comum não pode ganhar um aviso permanente.

    Um perfil de jogo da Steam com o número e mais nada é o desenho normal — e o
    aviso a cada abertura de editor viraria ruído que se aprende a ignorar.
    """
    assert exigencia_invisivel(MatchCriteria(window_class=["steam_app_1599660"])) == ""


def test_fora_do_jogo_da_steam_a_pagina_simples_nao_esconde_nada() -> None:
    """Só a página do "Jogo da Steam" tem campo escondido; as outras, não.

    Um `MatchCriteria` só com `process_name` é a página "Jogo" (um programa), e
    ali o valor ESTÁ na tela. Avisar seria mentir sobre estar escondido.
    """
    assert exigencia_invisivel(MatchCriteria(process_name=["cs2"])) == ""
    assert exigencia_invisivel(MatchCriteria(window_class=["firefox"])) == ""
    assert exigencia_invisivel(MatchAny()) == ""
    assert exigencia_invisivel(MatchManual()) == ""


def test_com_regex_de_titulo_o_editor_nao_abre_como_jogo_da_steam() -> None:
    """A fronteira exata do aviso, e ela foi MEDIDA, não suposta.

    As duas primeiras versões deste teste afirmavam que um perfil com
    `steam_app_*` MAIS `window_title_regex` ganharia o aviso do título. Estavam
    erradas, e o código estava certo: `_detect_steam_appid` exige `window_class`
    com um único `steam_app_<id>` e **nenhum** `window_title_regex`, então um
    perfil assim nem abre na página "Jogo da Steam" — ele cai no editor onde os
    campos ESTÃO visíveis. Avisar ali seria dizer que está escondido o que está
    na tela.

    O ramo do título dentro de `exigencia_invisivel` fica como cinto declarado:
    ele só passa a ter efeito se um dia o `_detect_steam_appid` afrouxar, e neste
    teste está escrito o que isso significaria.
    """
    match = MatchCriteria(
        window_class=["steam_app_3357650"], window_title_regex="PRAGMATA"
    )
    assert exigencia_invisivel(match) == ""


def test_o_appid_com_process_name_e_o_unico_caso_de_hoje() -> None:
    """Uma frase só, mesmo com mais de um valor invisível.

    Duas exigências não podem virar duas linhas soltas na tela; e hoje o único
    caminho que produz aviso é `steam_app_<id>` + `process_name`, que é
    exatamente o do perfil dela.
    """
    texto = exigencia_invisivel(
        MatchCriteria(
            window_class=["steam_app_3357650"],
            process_name=["PRAGMATA.exe", "Pragmata-Win64-Shipping.exe"],
        )
    )
    assert texto.count("Este perfil também exige") == 1
    assert '"PRAGMATA.exe", "Pragmata-Win64-Shipping.exe"' in texto


@pytest.mark.parametrize("nomes", [["a.exe"], ["a.exe", "b.exe", "c.exe"]])
def test_todos_os_valores_aparecem_nunca_um_resumo(nomes: list[str]) -> None:
    """"e mais 2" faria ela procurar no editor avançado o que já cabia aqui."""
    texto = exigencia_invisivel(
        MatchCriteria(window_class=["steam_app_1"], process_name=nomes)
    )
    for nome in nomes:
        assert f'"{nome}"' in texto


# ---------------------------------------------------------------------------
# O que NÃO pode ter mudado
# ---------------------------------------------------------------------------


def test_salvar_pela_pagina_simples_continua_preservando_o_invisivel() -> None:
    """A decisão de 10/08 fica inteira — este arquivo só a torna audível.

    `from_simple_choice` preserva o `process_name` do disco quando o editor
    simples salva. Se esta cura tivesse virado "apagar o que a tela não mostra",
    salvar o perfil pela janela destruiria a regra dela em silêncio — o defeito
    oposto, e pior.

    Morde ao fazer `from_simple_choice` ignorar a `regra_do_disco`.
    """
    novo = from_simple_choice("steam_game", "3357650", regra_do_disco=PRAGMATA)
    assert isinstance(novo, MatchCriteria)
    assert novo.window_class == ["steam_app_3357650"]
    assert novo.process_name == ["PRAGMATA.exe"], (
        "salvar pela página simples apagou o campo que ela não vê"
    )
    # E o que foi preservado é exatamente o que o aviso declara.
    assert "PRAGMATA.exe" in exigencia_invisivel(novo)
