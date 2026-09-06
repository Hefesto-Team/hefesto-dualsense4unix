"""`humanize_binding` e `dehumanize_binding` são INVERSAS — e não eram.

Medido em 06/09/2026, pela `NAVEGACAO-TECLAS-01` e conferido na costura:

    humanize_binding("KEY_F5")   -> "F5"    (o ramo de fallback, `tok[4:]`)
    dehumanize_binding("F5")     -> "F5"    (não voltava a ser tecla)
    parse_binding("F5")          -> ValueError

O buraco alcançava **F1..F12, Home, End, Insert, PageUp, PageDown, Comma, Dot e
as três de volume** — tudo o que o teclado virtual declara e o `_KEY_LABELS` não
nomeia. Na janela antiga era defeito VIVO: a coluna "Tecla do teclado" mostrava
`F5` e recusava `F5` digitado de volta, com um toast, sem ninguém ter mudado
nada. Na aba nova havia um contorno declarado, que era um segundo dono.

A CURA É NO DONO, e esta régua mede o que ela promete: **o que a tela mostra, a
tela aceita de volta**. Ela não digita nenhuma tecla nova — as duas listas saem
do próprio módulo e do vocabulário do `evdev`.

MORDIDA (06/09/2026, com a saída): tire o ramo `elif _e_nome_de_tecla(tok)` de
`input_actions.dehumanize_binding` e `test_o_que_a_tela_mostra_a_tela_aceita`
reprova nomeando as teclas que deixaram de voltar; faça `_e_nome_de_tecla`
devolver `True` sempre e `test_o_que_o_evdev_nao_conhece_nao_vira_tecla`
reprova, porque `banana` viraria `KEY_BANANA` e a recusa perderia o nome dela.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions import input_actions
from hefesto_dualsense4unix.core.keyboard_mappings import parse_binding


def _teclas_que_a_tela_pode_mostrar() -> list[str]:
    """Todo `KEY_*` que o teclado virtual declara — perguntado ao dono.

    É a lista de capacidades que o device anuncia ao `uinput`, e por isso é a
    lista do que a coluna "Tecla do teclado" pode chegar a mostrar.
    """
    from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS

    return sorted(k for k in SUPPORTED_KEYS if k.startswith("KEY_"))


def test_o_que_a_tela_mostra_a_tela_aceita() -> None:
    """Ida e volta fechada, tecla por tecla, sem uma única digitada aqui."""
    perdidas = []
    for cru in _teclas_que_a_tela_pode_mostrar():
        na_tela = input_actions.humanize_binding(cru)
        de_volta = input_actions.dehumanize_binding(na_tela)
        if de_volta != cru:
            perdidas.append(f"{cru} → {na_tela!r} → {de_volta!r}")
    assert not perdidas, (
        "estas teclas aparecem na tela e não voltam do jeito que foram — a tela "
        "recusaria o que ela mesma escreveu:\n  " + "\n  ".join(perdidas))


def test_o_que_volta_o_parse_binding_aceita() -> None:
    """A volta não basta ser igual: ela tem de passar na fronteira."""
    for cru in _teclas_que_a_tela_pode_mostrar():
        de_volta = input_actions.dehumanize_binding(
            input_actions.humanize_binding(cru))
        assert parse_binding(de_volta) == (cru,), de_volta


def test_o_combo_tambem_fecha() -> None:
    """O separador é `+` dos dois lados, e o combo é o caso que ela digita."""
    for cru in ("KEY_LEFTALT+KEY_TAB", "KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T",
                "KEY_LEFTCTRL+KEY_F5"):
        assert input_actions.dehumanize_binding(
            input_actions.humanize_binding(cru)) == cru


def test_o_que_o_evdev_nao_conhece_nao_vira_tecla() -> None:
    """Um nome inventado segue CRU, e a recusa continua dizendo o nome dela.

    Sem esta guarda, `banana` viraria `KEY_BANANA`: o `parse_binding` deixaria
    passar (ele só exige o prefixo), e a recusa cairia lá adiante, com outro
    nome e em outra tela.
    """
    assert input_actions.dehumanize_binding("banana") == "banana"
    with pytest.raises(ValueError, match="BANANA"):
        parse_binding(input_actions.dehumanize_binding("banana"))


def test_a_aba_pergunta_ao_dono_em_vez_de_traduzir_de_novo() -> None:
    """O contorno da aba 06 virou delegação — uma tradução, um dono.

    MORDIDA: devolva à `_desfazer_o_humanize` uma tabela própria e esta régua
    reprova, porque as duas respostas passam a poder divergir sem ninguém ver.
    """
    from hefesto_dualsense4unix.interface.pacotes import a06_navegacao

    for cru in _teclas_que_a_tela_pode_mostrar():
        na_tela = input_actions.humanize_binding(cru)
        assert (a06_navegacao._desfazer_o_humanize(na_tela)
                == input_actions.dehumanize_binding(na_tela))
