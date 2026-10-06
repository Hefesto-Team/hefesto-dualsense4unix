"""A-REGRA-QUE-A-TELA-NAO-MOSTRA-01 — o editor afirmava uma regra que não era a regra."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    CAMINHO_DA_JANELA_GTK,
    exigencia_invisivel,
    from_simple_choice,
)

PRAGMATA = MatchCriteria(
    window_class=["steam_app_3357650"], process_name=["PRAGMATA.exe"]
)


def test_o_caso_dela_e_declarado_com_o_campo_e_o_valor() -> None:
    """A cura. Morde ao fazer `exigencia_invisivel` devolver "" sempre."""
    texto = exigencia_invisivel(PRAGMATA)
    assert "nome do processo" in texto, "o rótulo tem de ser o do editor avançado"
    assert '"PRAGMATA.exe"' in texto, "o valor exato, para ela reconhecer"
    assert "Modo avançado" not in texto, (
        "o matcher voltou a nomear um botão da janela GTK")
    assert CAMINHO_DA_JANELA_GTK, "o caminho da janela GTK perdeu o dono"
    assert "Modo avançado" in CAMINHO_DA_JANELA_GTK


def test_a_frase_nao_manda_apagar_nada() -> None:
    """Quem escreveu o critério foi ela; a decisão de mudá-lo é do usuário."""
    texto = exigencia_invisivel(PRAGMATA).lower()
    for proibido in ("apague", "remova", "errado", "incorreto", "proton", "wine"):
        assert proibido not in texto


def test_sem_campo_invisivel_a_linha_nao_existe() -> None:
    """O caso comum não pode ganhar um aviso permanente."""
    assert exigencia_invisivel(MatchCriteria(window_class=["steam_app_1599660"])) == ""


def test_fora_do_jogo_da_steam_a_pagina_simples_nao_esconde_nada() -> None:
    """Só a página do "Jogo da Steam" tem campo escondido; as outras, não."""
    assert exigencia_invisivel(MatchCriteria(process_name=["cs2"])) == ""
    assert exigencia_invisivel(MatchCriteria(window_class=["firefox"])) == ""
    assert exigencia_invisivel(MatchAny()) == ""
    assert exigencia_invisivel(MatchManual()) == ""


def test_com_regex_de_titulo_o_editor_nao_abre_como_jogo_da_steam() -> None:
    """A fronteira exata do aviso, e ela foi MEDIDA, não suposta."""
    match = MatchCriteria(
        window_class=["steam_app_3357650"], window_title_regex="PRAGMATA"
    )
    assert exigencia_invisivel(match) == ""


def test_o_appid_com_process_name_e_o_unico_caso_de_hoje() -> None:
    """Uma frase só, mesmo com mais de um valor invisível."""
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


def test_salvar_pela_pagina_simples_continua_preservando_o_invisivel() -> None:
    """A decisão de 10/08 fica inteira — este arquivo só a torna audível.

    `from_simple_choice` preserva o `process_name` do disco quando o editor
    simples salva. Se esta cura tivesse virado "apagar o que a tela não mostra",
    salvar o perfil pela janela destruiria a regra de produto em silêncio — o defeito
    oposto, e pior.

    Morde ao fazer `from_simple_choice` ignorar a `regra_do_disco`.
    """
    novo = from_simple_choice("steam_game", "3357650", regra_do_disco=PRAGMATA)
    assert isinstance(novo, MatchCriteria)
    assert novo.window_class == ["steam_app_3357650"]
    assert novo.process_name == ["PRAGMATA.exe"], (
        "salvar pela página simples apagou o campo que ela não vê"
    )
    assert "PRAGMATA.exe" in exigencia_invisivel(novo)
