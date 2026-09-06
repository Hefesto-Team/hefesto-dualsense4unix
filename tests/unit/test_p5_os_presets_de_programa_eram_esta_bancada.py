"""P5 — os três botões de programa cobriam DOZE programas, e eram os desta bancada.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/5 (24/08/2026). As listas de
`SIMPLE_MATCH_PRESETS` eram, literalmente:

    "browser":  ["firefox", "chromium", "brave", "google-chrome"]
    "terminal": ["gnome-terminal", "alacritty", "kitty", "konsole"]
    "editor":   ["code", "zed", "neovide"]

Doze programas, escolhidos em julho, e eram os programas instalados NESTA
máquina. O preço não é teórico e não tem sintoma: quem instala outro terminal,
clica "Terminal" e salva ganha um perfil que **nunca casa** — `matches()`
devolve `False` em silêncio, o perfil não entra, e não há erro nenhum a ler.

O caso mais caro é o `ptyxis`: é o terminal padrão do COSMIC, que é o desktop
DESTA máquina — o botão "Terminal" já não cobria o terminal da própria casa.

**O que este arquivo NÃO afirma.** Que a lista de hoje é completa. Nenhuma
lista de programas fecha; o que ela pode ser é DECLARADA, com dono e com data
(§P5: *"nada de detecção mágica"*). Estes testes travam o que já foi medido
faltando, e o `test_a_lista_e_declarada_e_nao_adivinhada` trava o método.

A ida-e-volta é a segunda metade, e é a que impede a cura de virar defeito: um
perfil "Terminal" salvo em JULHO tem os quatro nomes daquele dia no disco, e
`detect_simple_preset` compara por igualdade EXATA de conjunto. Sem
`_PRESETS_HISTORICOS`, crescer a lista rebaixaria todo perfil antigo dela para
o editor avançado — sem ninguém ter mexido em nada, e sem uma palavra na tela.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria
from hefesto_dualsense4unix.profiles.simple_match import (
    SIMPLE_MATCH_PRESETS,
    detect_simple_preset,
    from_simple_choice,
)

#: Os programas que REPROVAVAM em 25/08/2026, antes de qualquer linha de cura,
#: com o `matches()` do esquema. Cada um é um (preset, wm_class) medido.
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
    """`ptyxis` tem teste próprio porque é o buraco medido mais caro.

    É o terminal padrão do COSMIC — o desktop desta máquina. O botão "Terminal"
    não cobria o terminal da casa que escreveu o botão.
    """
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
    """Nenhum programa pode casar com dois botões ao mesmo tempo.

    Se `vivaldi` casasse com "Navegador" E com "Editor", a disputa entre dois
    perfis dela passaria a depender de prioridade num empate que ninguém pediu
    — e a tela não teria como explicar por quê.
    """
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
    """Os três presets continuam sendo LISTA de `window_class`, nada mais.

    O método é o que este teste trava. Adivinhar "isto é um editor" pelo nome
    do processo acerta na bancada de quem escreveu e erra no computador de quem
    usa, sem jeito de a pessoa ver por quê — é a classe de contorno que esta
    casa recusa (§P5). Se um dia alguém somar `window_title_regex` ou
    `process_name` a um destes três, este teste reprova e a decisão volta para
    a mesa.
    """
    for chave in ("browser", "terminal", "editor"):
        regra = SIMPLE_MATCH_PRESETS[chave]
        assert isinstance(regra, MatchCriteria)
        assert regra.window_class, f"'{chave}' ficou sem lista"
        assert not regra.window_title_regex, f"'{chave}' ganhou regex de título"
        assert not regra.process_name, f"'{chave}' ganhou nome de processo"


# --- A ida-e-volta: o perfil que já está no disco dela ---------------------


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
    """MORDE `_PRESETS_HISTORICOS`: sem ele o perfil dela cai no avançado.

    Este é o teste que impede a cura de virar defeito. Arranque a chamada a
    `_preset_historico` em `detect_simple_preset` e ele reprova devolvendo
    `None` — que na aba é o seletor "Aplica a" rebaixado para o editor
    avançado, num perfil em que ela não tocou.
    """
    do_disco = MatchCriteria(window_class=list(de_julho))
    assert detect_simple_preset(do_disco) == chave


def test_a_escrita_grava_a_lista_de_hoje() -> None:
    """Só a LEITURA é tolerante — o Salvar alarga o perfil, nunca o encolhe.

    Reabrir um "Terminal" de julho e salvar grava os terminais de hoje, que é
    exatamente o que o rótulo "Terminal" promete. Alargar nunca tira dela um
    casamento que ela já tinha (o `test_os_doze_de_julho_continuam_casando`
    responde por essa metade).
    """
    gravado = from_simple_choice("terminal")
    assert isinstance(gravado, MatchCriteria)
    assert "ptyxis" in gravado.window_class
    assert len(gravado.window_class) > 4


def test_o_historico_nao_engole_perfil_com_campo_invisivel() -> None:
    """Lista de julho MAIS um `process_name` não é preset — é regra dela.

    A página simples não sabe mostrar `process_name`, e reconhecer este perfil
    como "Terminal" faria a tela mostrar uma regra que não é a regra do perfil
    — o defeito exato que o `exigencia_invisivel` existe para não repetir.
    """
    com_invisivel = MatchCriteria(
        window_class=["gnome-terminal", "alacritty", "kitty", "konsole"],
        process_name=["alacritty"],
    )
    assert detect_simple_preset(com_invisivel) is None


def test_o_que_nao_e_preset_nenhum_continua_sendo_none() -> None:
    """A guarda que impede o histórico de virar um `any` disfarçado.

    O EXEMPLO MUDOU EM 06/09/2026, e a régua não afrouxou. `window_class=["obs"]`
    era *preset nenhum* até a `ONDA5-10-01` criar a SEXTA forma — "janela", uma
    classe de janela SÓ, espelho do "game" —, e passou a ter nome. Um exemplo
    que envelhece assim é o caso BOM: alguém trabalhou. O que esta régua mede é
    a guarda, então o exemplo passa a ser um critério que NENHUMA das seis
    formas cobre: dois campos preenchidos ao mesmo tempo, que não é "janela"
    (classe só) nem "game" (programa só) nem preset fixo nenhum.
    """
    assert detect_simple_preset(
        MatchCriteria(window_class=["obs"], process_name=["obs-studio"])) is None
    assert detect_simple_preset(MatchAny()) == "any"
