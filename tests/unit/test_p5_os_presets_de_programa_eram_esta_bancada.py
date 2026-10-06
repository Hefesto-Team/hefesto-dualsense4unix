"""P5 — os três botões de programa cobriam DOZE programas, e eram os desta bancada."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria
from hefesto_dualsense4unix.profiles.simple_match import (
    SIMPLE_MATCH_PRESETS,
    detect_simple_preset,
    from_simple_choice,
)

OS_QUE_REPROVAVAM = [
    ("terminal", "ptyxis"),
    ("terminal", "foot"),
    ("terminal", "wezterm"),
    ("terminal", "xterm"),
    ("browser", "vivaldi"),
    ("browser", "zen"),
    ("browser", "org.gnome.Epiphany"),
    ("editor", "gedit"),
    ("editor", "org.kde.kate"),
    ("editor", "emacs"),
    ("editor", "vim"),
]


def _casa(preset: str, wm_class: str) -> bool:
    regra = SIMPLE_MATCH_PRESETS[preset]
    return bool(regra.matches({"wm_class": wm_class}))


@pytest.mark.parametrize(("preset", "programa"), OS_QUE_REPROVAVAM)
def test_o_programa_que_nao_casava_casa(preset: str, programa: str) -> None:
    """MORDE a lista: arranque a entrada e o perfil volta a nunca entrar."""
    assert _casa(preset, programa), (
        f"o botão '{preset}' não cobre '{programa}': o perfil salvo por esse "
        "botão nunca entra, e a tela não diz nada"
    )


def test_o_terminal_desta_maquina_entra_no_botao_terminal() -> None:
    """`ptyxis` tem teste próprio porque é o buraco medido mais caro."""
    assert _casa("terminal", "ptyxis")


def test_os_doze_de_julho_continuam_casando() -> None:
    """Crescer a lista não pode TIRAR ninguém — isso seria regressão calada."""
    de_julho = [
        ("browser", "firefox"),
        ("browser", "chromium"),
        ("browser", "brave"),
        ("browser", "google-chrome"),
        ("terminal", "gnome-terminal"),
        ("terminal", "alacritty"),
        ("terminal", "kitty"),
        ("terminal", "konsole"),
        ("editor", "code"),
        ("editor", "zed"),
        ("editor", "neovide"),
    ]
    faltando = [(p, c) for p, c in de_julho if not _casa(p, c)]
    assert faltando == [], f"a lista nova PERDEU programas de julho: {faltando}"


def test_os_tres_botoes_nao_se_misturam() -> None:
    """Nenhum programa pode casar com dois botões ao mesmo tempo."""
    chaves = ("browser", "terminal", "editor")
    vistos: dict[str, str] = {}
    duplicados: list[tuple[str, str, str]] = []
    for chave in chaves:
        regra = SIMPLE_MATCH_PRESETS[chave]
        assert isinstance(regra, MatchCriteria)
        for programa in regra.window_class:
            baixo = programa.lower()
            if baixo in vistos:
                duplicados.append((programa, vistos[baixo], chave))
            vistos[baixo] = chave
    assert duplicados == [], f"programa em dois botões: {duplicados}"


def test_a_lista_e_declarada_e_nao_adivinhada() -> None:
    """Os três presets continuam sendo LISTA de `window_class`, nada mais."""
    for chave in ("browser", "terminal", "editor"):
        regra = SIMPLE_MATCH_PRESETS[chave]
        assert isinstance(regra, MatchCriteria)
        assert regra.window_class, f"'{chave}' ficou sem lista"
        assert not regra.window_title_regex, f"'{chave}' ganhou regex de título"
        assert not regra.process_name, f"'{chave}' ganhou nome de processo"


@pytest.mark.parametrize(
    ("chave", "de_julho"),
    [
        ("browser", ["firefox", "chromium", "brave", "google-chrome"]),
        ("terminal", ["gnome-terminal", "alacritty", "kitty", "konsole"]),
        ("editor", ["code", "zed", "neovide"]),
    ],
)
def test_o_perfil_de_julho_continua_abrindo_na_pagina_simples(
    chave: str, de_julho: list[str]
) -> None:
    """MORDE `_PRESETS_HISTORICOS`: sem ele o perfil do usuário cai no avançado."""
    do_disco = MatchCriteria(window_class=list(de_julho))
    assert detect_simple_preset(do_disco) == chave


def test_a_escrita_grava_a_lista_de_hoje() -> None:
    """Só a LEITURA é tolerante — o Salvar alarga o perfil, nunca o encolhe."""
    gravado = from_simple_choice("terminal")
    assert isinstance(gravado, MatchCriteria)
    assert "ptyxis" in gravado.window_class
    assert len(gravado.window_class) > 4


def test_o_historico_nao_engole_perfil_com_campo_invisivel() -> None:
    """Lista de julho MAIS um `process_name` não é preset — é regra de produto."""
    com_invisivel = MatchCriteria(
        window_class=["gnome-terminal", "alacritty", "kitty", "konsole"],
        process_name=["alacritty"],
    )
    assert detect_simple_preset(com_invisivel) is None


def test_o_que_nao_e_preset_nenhum_continua_sendo_none() -> None:
    """A guarda que impede o histórico de virar um `any` disfarçado."""
    assert detect_simple_preset(
        MatchCriteria(window_class=["obs"], process_name=["obs-studio"])) is None
    assert detect_simple_preset(MatchAny()) == "any"
