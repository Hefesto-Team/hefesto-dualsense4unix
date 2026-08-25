"""PERFIS-ABRE-O-QUE-GUARDA-01/P5 — os três botões cobriam DOZE programas.

Medido em 25/08/2026, antes de qualquer linha de cura, com o ``matches()`` do
esquema contra as listas de então (``simple_match.py:49-55``):

    "browser":  ["firefox", "chromium", "brave", "google-chrome"]
    "terminal": ["gnome-terminal", "alacritty", "kitty", "konsole"]
    "editor":   ["code", "zed", "neovide"]

Onze programas reprovavam — entre eles o ``ptyxis``, que é o terminal padrão
do COSMIC, **o desktop desta máquina**. O preço não é teórico e não tem tela:
quem instala outro terminal, clica "Terminal" e salva ganha um perfil que
nunca casa. ``matches()`` devolve ``False`` em silêncio, não há erro a ler, e
a queixa que sobra é "o perfil não pega".

As três famílias de teste daqui, e cada uma morde uma cura diferente:

1. **A cobertura** — os onze medidos entram. Arranque a entrada da lista e o
   programa volta a não casar.
2. **O round-trip histórico** — um perfil salvo em JULHO, com a lista de doze
   gravada dentro dele, continua abrindo na página SIMPLES. Sem
   ``_PRESETS_HISTORICOS`` crescer as listas rebaixaria para o editor avançado
   todo "Navegador"/"Terminal"/"Editor" que já está no disco dela, sem
   ninguém ter mexido em nada. É a regressão que a cura de P5 poderia ter
   CRIADO, e é por isso que ela tem teste próprio.
3. **A higiene da lista** — sem duplicata (a comparação é sem caixa, então
   ``firefox`` e ``Firefox`` seriam a MESMA entrada duas vezes) e sem programa
   em duas famílias (um mesmo nome em "terminal" e "editor" faz
   ``detect_simple_preset`` devolver a família que o dicionário iterar
   primeiro — a tela passaria a mostrar um botão que ela não clicou).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles import simple_match as sm
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria

# ---------------------------------------------------------------------------
# 1. A cobertura — os onze que reprovavam em 25/08, com o nome de quem os usa
# ---------------------------------------------------------------------------

#: ``(wm_class que o compositor entrega, botão que tem de cobri-lo, por quê)``.
#: Todos reprovavam contra as listas de julho; o ``ptyxis`` é o caro.
OS_ONZE_QUE_REPROVAVAM: list[tuple[str, str, str]] = [
    ("ptyxis", "terminal", "o terminal padrão do COSMIC, o desktop desta máquina"),
    ("foot", "terminal", "o terminal de quem usa Wayland puro"),
    ("wezterm", "terminal", "terminal com configuração em Lua, comum entre devs"),
    ("xterm", "terminal", "o terminal que TODA instalação de X tem"),
    ("vivaldi", "browser", "navegador Chromium com nome próprio"),
    ("zen", "browser", "navegador Firefox com nome próprio"),
    ("org.gnome.Epiphany", "browser", "o navegador de fábrica do GNOME"),
    ("gedit", "editor", "o editor de texto de muita gente, e não é IDE"),
    ("org.kde.kate", "editor", "o editor de fábrica do KDE"),
    ("emacs", "editor", "editor de janela própria, não só de terminal"),
    ("vim", "editor", "com `gvim`/janela, é wm_class como qualquer outra"),
]


@pytest.mark.parametrize(
    ("programa", "botao", "porque"),
    OS_ONZE_QUE_REPROVAVAM,
    ids=[p for p, _, _ in OS_ONZE_QUE_REPROVAVAM],
)
def test_o_botao_cobre_o_programa(programa: str, botao: str, porque: str) -> None:
    """MORDE `_NAVEGADORES`/`_TERMINAIS`/`_EDITORES`: tire a entrada, reprova."""
    preset = sm.SIMPLE_MATCH_PRESETS[botao]
    assert isinstance(preset, MatchCriteria)
    assert preset.matches({"wm_class": programa}), (
        f"o botão “{botao}” não cobre `{programa}` — {porque}. Quem clicar nele "
        "e salvar ganha um perfil que nunca casa, sem uma palavra na tela."
    )


def test_o_botao_cobre_o_programa_com_a_caixa_do_compositor() -> None:
    """A mesma janela chega com caixas diferentes entre X e Wayland.

    O Firefox é ``firefox`` no Wayland nativo e ``Navigator`` sob XWayland; o
    ``wm_class`` chega com a caixa que o toolkit escolheu. A comparação do
    esquema é sem caixa (`_casa_sem_caixa`), e este teste trava isso pelo lado
    do preset: se alguém trocar as listas por uma comparação exata, reprova.
    """
    navegador = sm.SIMPLE_MATCH_PRESETS["browser"]
    assert isinstance(navegador, MatchCriteria)
    for grafia in ("Firefox", "FIREFOX", "navigator", "Navigator"):
        assert navegador.matches({"wm_class": grafia}), grafia


def test_o_botao_nao_cobre_quem_nao_e_da_familia() -> None:
    """Régua que só sabe passar não é régua: o preset também tem de RECUSAR."""
    for botao, intruso in (
        ("terminal", "firefox"),
        ("browser", "ptyxis"),
        ("editor", "vivaldi"),
    ):
        preset = sm.SIMPLE_MATCH_PRESETS[botao]
        assert isinstance(preset, MatchCriteria)
        assert not preset.matches({"wm_class": intruso}), (
            f"o botão “{botao}” casou com `{intruso}`, que é de outra família"
        )


def test_janela_sem_wm_class_nunca_casa() -> None:
    """Ausência de evidência não é igualdade — a regra do `_casa_sem_caixa`."""
    for botao in ("browser", "terminal", "editor"):
        preset = sm.SIMPLE_MATCH_PRESETS[botao]
        assert isinstance(preset, MatchCriteria)
        assert not preset.matches({"wm_class": ""})
        assert not preset.matches({})


# ---------------------------------------------------------------------------
# 2. O round-trip histórico — o perfil de JULHO continua abrindo na página
#    simples. Esta é a regressão que crescer as listas poderia ter criado.
# ---------------------------------------------------------------------------

#: As três listas EXATAS de antes de 25/08/2026, copiadas do §2.2/5 da sprint.
AS_LISTAS_DE_JULHO: dict[str, list[str]] = {
    "browser": ["firefox", "chromium", "brave", "google-chrome"],
    "terminal": ["gnome-terminal", "alacritty", "kitty", "konsole"],
    "editor": ["code", "zed", "neovide"],
}


@pytest.mark.parametrize("botao", sorted(AS_LISTAS_DE_JULHO))
def test_o_perfil_de_julho_continua_abrindo_na_pagina_simples(botao: str) -> None:
    """MORDE `_PRESETS_HISTORICOS`: apague o dicionário e reprova com `None`.

    ``None`` é o editor AVANÇADO com o seletor rebaixado a "Vale sempre" — a
    tela mostrando uma regra que não é a regra, que é o defeito que a
    `O-AVANCADO-QUE-MOSTRAVA-VAZIO-01` já mediu por outro caminho.
    """
    do_disco = MatchCriteria(window_class=list(AS_LISTAS_DE_JULHO[botao]))
    assert sm.detect_simple_preset(do_disco) == botao


@pytest.mark.parametrize("botao", sorted(AS_LISTAS_DE_JULHO))
def test_o_perfil_de_hoje_tambem_abre_na_pagina_simples(botao: str) -> None:
    """O round-trip de HOJE: gravar pelo botão e reabrir devolve o botão."""
    gravado = sm.from_simple_choice(botao)
    assert sm.detect_simple_preset(gravado) == botao


@pytest.mark.parametrize("botao", sorted(AS_LISTAS_DE_JULHO))
def test_a_escrita_grava_sempre_a_lista_de_hoje(botao: str) -> None:
    """Só a LEITURA é tolerante — reabrir e salvar ALARGA para os de hoje.

    Alargar nunca tira dela um casamento que já tinha (a lista de julho é
    subconjunto da de hoje), e é o que o rótulo "Terminal" promete.
    """
    gravado = sm.from_simple_choice(botao)
    assert isinstance(gravado, MatchCriteria)
    de_julho = set(AS_LISTAS_DE_JULHO[botao])
    de_hoje = set(gravado.window_class)
    assert de_julho <= de_hoje, f"a lista de hoje PERDEU {sorted(de_julho - de_hoje)}"
    assert len(de_hoje) > len(de_julho), "a lista não cresceu"


def test_o_historico_nao_reconhece_o_que_tem_campo_invisivel() -> None:
    """Um "Terminal" de julho com `process_name` somado à mão fica no avançado.

    A página simples não sabe MOSTRAR esse campo, e reconhecê-la como preset
    faria o Salvar seguinte apagá-lo calado — a mesma disciplina do
    `exigencia_invisivel`.
    """
    com_extra = MatchCriteria(
        window_class=list(AS_LISTAS_DE_JULHO["terminal"]),
        process_name=["tmux"],
    )
    assert sm.detect_simple_preset(com_extra) is None


# ---------------------------------------------------------------------------
# 3. A higiene das listas
# ---------------------------------------------------------------------------

AS_TRES_FAMILIAS = ("browser", "terminal", "editor")


@pytest.mark.parametrize("botao", AS_TRES_FAMILIAS)
def test_a_lista_nao_repete_programa(botao: str) -> None:
    """Sem caixa, `Firefox` e `firefox` são a MESMA entrada — duas seria ruído."""
    preset = sm.SIMPLE_MATCH_PRESETS[botao]
    assert isinstance(preset, MatchCriteria)
    vistos: dict[str, str] = {}
    repetidos: list[tuple[str, str]] = []
    for nome in preset.window_class:
        chave = nome.casefold()
        if chave in vistos:
            repetidos.append((vistos[chave], nome))
        vistos[chave] = nome
    assert not repetidos, f"entradas repetidas sem caixa em “{botao}”: {repetidos}"


def test_nenhum_programa_mora_em_duas_familias() -> None:
    """Um nome em duas listas faz o botão detectado depender da ordem do dict.

    E aí a tela mostra um botão que ela não clicou, sem nada explicando.
    """
    por_programa: dict[str, list[str]] = {}
    for botao in AS_TRES_FAMILIAS:
        preset = sm.SIMPLE_MATCH_PRESETS[botao]
        assert isinstance(preset, MatchCriteria)
        for nome in preset.window_class:
            por_programa.setdefault(nome.casefold(), []).append(botao)
    colididos = {n: fs for n, fs in por_programa.items() if len(fs) > 1}
    assert not colididos, f"programa em mais de uma família: {colididos}"


def test_a_lista_cresceu_de_verdade_em_relacao_a_bancada_de_julho() -> None:
    """O número que a sprint mediu: DOZE programas nos três botões somados."""
    total = sum(
        len(sm.SIMPLE_MATCH_PRESETS[b].window_class)  # type: ignore[union-attr]
        for b in AS_TRES_FAMILIAS
    )
    assert total > 12, f"os três botões somam {total} programas — ainda a bancada"


def test_o_botao_desconhecido_continua_caindo_no_sempre() -> None:
    """O contrato antigo do `from_simple_choice` não mudou com P5."""
    assert isinstance(sm.from_simple_choice("nao_existe"), MatchAny)
    assert sm.detect_simple_preset(MatchAny()) == "any"
