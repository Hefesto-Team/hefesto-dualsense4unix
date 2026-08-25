"""NO-JOGO-SEM-FALSO-VERDE-01/T7 — a cor das seis linhas, com GTK de verdade.

**O que estava medido, e é o defeito inteiro:** o `COR_DA_SITUACAO` aparecia em
`tests/` exatamente duas vezes, as duas em COMENTÁRIO, e nenhuma vez numa
asserção. O ramo que pinta (`painel_no_jogo`, o `set_markup` do `atualizar`) só
existe na classe REAL — o dublê sem GTK guarda as `LinhaDoJogo` e não pinta nada
—, e o único teste que instanciava o painel com GTK de verdade olhava para a
geometria, não para a cor.
Resultado: trocar o `set_markup` por um `set_text` passava nos 110 testes desta
aba, e a tela saía com "no jogo agora" em branco, exatamente como a primeira
foto desta aba saiu em 10/08.

A cor não é enfeite aqui. Ela é a única coisa que se lê de relance numa tabela
de seis linhas, e as duas que ganham cor são as duas que afirmam alguma coisa —
verde para *"está chegando"*, amarelo para *"era para estar chegando e não
está"*. As outras três EXPLICAM, e ficam apagadas de propósito.

**Por que markup e não classe de CSS**, para quem vier alargar isto: está medido
na docstring de `COR_DA_SITUACAO`. A regra `.hefesto-dualsense4unix-window
label` do `theme.css` tem especificidade MAIOR que a de
`.hefesto-dualsense4unix-status-ok` — a classe é aplicada, existe no contexto, e
não pinta um pixel. Um teste que só perguntasse "a classe está lá?" passaria com
a tela em branco; é por isso que esta bancada lê o MARKUP.
"""

from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("a cor das linhas da aba No jogo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta — `gi` existe sem as
# typelibs no runner do CI, e o ImportError na COLETA derruba a suíte inteira.
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets.controller_card import (
    SITUACAO_CHEGANDO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    COR_DA_SITUACAO,
    PALAVRA_DA_SITUACAO,
    PainelNoJogo,
)

#: `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
#: janelas, e uma `Gtk.Window` fica 1x1 para sempre. É armadilha já paga desta
#: casa (COMO-OLHAR-A-TELA.md).
_janelas_vivas: list[Any] = []

#: O controle primário — o caso de mesa de um controle só.
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "player": 1,
    "player_slot": 1,
}

#: Idade, em segundos, de um carimbo que já morreu. `ATIVIDADE_FRESCA_S` é 3,0.
_VELHO = 30.0


def _estado(visto: dict[str, Any], **vpad_extra: Any) -> dict[str, Any]:
    """Um `state_full` mínimo com o vpad do jogador 1 e os carimbos pedidos."""
    vpad: dict[str, Any] = {"player": 1, "visto_ha_s": dict(visto)}
    vpad.update(vpad_extra)
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(_ENTRY)],
        "rumble_ff": {"per_vpad": [vpad]},
    }


def _painel_pintado(state: dict[str, Any]) -> PainelNoJogo:
    """Um painel REAL, dentro de uma janela, já repintado com ``state``."""
    painel = PainelNoJogo()
    janela = Gtk.OffscreenWindow()
    janela.add(painel)
    janela.show_all()
    _janelas_vivas.append(janela)
    painel.atualizar(_ENTRY, state)
    return painel


def _valor(painel: PainelNoJogo, recurso: str) -> Any:
    """O rótulo da coluna da DIREITA de um recurso — o que ganha cor."""
    _rotulo, valor = painel._linhas[recurso]
    return valor


# ---------------------------------------------------------------------------
# As duas linhas que ganham cor
# ---------------------------------------------------------------------------


def test_a_linha_que_esta_chegando_sai_verde() -> None:
    """"no jogo agora" é a única frase desta tela que afirma coisa boa.

    Arranque para ver reprovar: trocar o `valor.set_markup(...)` de
    `PainelNoJogo.atualizar` por `valor.set_text(linha.texto)`. Hoje isso passa
    nos 110 testes desta aba, e a tela sai em branco.
    """
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))

    valor = _valor(painel, "touchpad")

    assert valor.get_use_markup() is True
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO]


def test_a_linha_que_parou_sai_amarela() -> None:
    """E "parou" pede atenção: era para estar chegando e não está.

    Amarelo e não vermelho, e a razão está na docstring de `COR_DA_SITUACAO`:
    vermelho ensinaria ela a ver avaria onde há um jogo que parou de pedir.

    Arranque para ver reprovar: a mesma troca de `set_markup` por `set_text`.
    """
    painel = _painel_pintado(_estado({"touchpad_click": _VELHO}))

    valor = _valor(painel, "touchpad")

    assert valor.get_use_markup() is True
    assert COR_DA_SITUACAO[SITUACAO_PARADO] in valor.get_label()
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_PARADO]


def test_as_duas_cores_nao_sao_a_mesma() -> None:
    """A régua sabe distinguir as duas — senão um `COR_DA_SITUACAO` de uma cor
    só passaria nos dois testes acima e a tabela leria como um bloco monocromo.
    """
    verde = _valor(
        _painel_pintado(_estado({"touchpad_click": 0.5})), "touchpad"
    ).get_label()
    amarela = _valor(
        _painel_pintado(_estado({"touchpad_click": _VELHO})), "touchpad"
    ).get_label()

    assert verde != amarela


# ---------------------------------------------------------------------------
# E as três que EXPLICAM, e ficam apagadas
# ---------------------------------------------------------------------------


def test_a_linha_sem_pedido_fica_apagada_e_sem_cor() -> None:
    """"sem pedido ainda" é explicação, não defeito: apagada, e sem markup.

    As duas metades importam. Sem a classe, a linha compete de igual para igual
    com as que afirmam alguma coisa; com um `<span>` de cor, ela vira uma
    terceira cor numa tabela que decidiu ter duas.

    Arranque para ver reprovar: pôr `SITUACAO_NUNCA` em `COR_DA_SITUACAO`.
    """
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))

    valor = _valor(painel, "lightbar")

    assert valor.get_style_context().has_class("dim-label")
    assert valor.get_use_markup() is False
    assert valor.get_text() == PALAVRA_DA_SITUACAO[SITUACAO_NUNCA]


def test_a_linha_que_acorda_perde_o_apagado() -> None:
    """O painel REUSA os mesmos seis rótulos a cada tique — e a classe gruda.

    Este é o defeito que só aparece no segundo tique, e por isso é o mais fácil
    de deixar passar: a linha nasce "sem pedido ainda" (apagada), o jogo começa
    a pedir, ela vira "no jogo agora" com o `<span>` verde — e continua com a
    `dim-label` por cima, porque ninguém a tirou. Verde apagado em cima de fundo
    escuro é o que a primeira foto desta aba mostrou.

    Arranque para ver reprovar: tirar o `contexto.remove_class("dim-label")` do
    ramo colorido de `PainelNoJogo.atualizar`.
    """
    painel = _painel_pintado(_estado({}))
    valor = _valor(painel, "touchpad")
    assert valor.get_style_context().has_class("dim-label")

    painel.atualizar(_ENTRY, _estado({"touchpad_click": 0.5}))

    assert valor.get_style_context().has_class("dim-label") is False
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()


def test_a_linha_que_adormece_volta_a_ficar_apagada() -> None:
    """E o caminho de volta, que é a contraprova do de cima.

    Régua que só sabe passar numa direção não é régua: uma cura que nunca mais
    aplicasse a `dim-label` passaria no teste anterior.
    """
    painel = _painel_pintado(_estado({"touchpad_click": 0.5}))
    valor = _valor(painel, "touchpad")
    assert valor.get_style_context().has_class("dim-label") is False

    painel.atualizar(_ENTRY, _estado({}))

    assert valor.get_style_context().has_class("dim-label")
    assert valor.get_use_markup() is False


# ---------------------------------------------------------------------------
# O texto não pode ser comido pelo markup
# ---------------------------------------------------------------------------


def test_o_numero_dos_motores_sobrevive_a_pintura() -> None:
    """A frase mais longa desta coluna, colorida, tem de chegar inteira à tela.

    `get_text()` devolve o texto JÁ sem as marcas — se o `escapar_markup` ou o
    `<span>` comesse um pedaço, é aqui que aparece. E o parêntese com o número é
    a metade que a MOTOR-QUE-NAO-SE-VE-01 pagou para existir.
    """
    state = _estado(
        {"rumble": 0.5},
        rumble_no_fisico=[255, 255],
        # O par só entra na frase se for FRESCO — a idade viaja separada, e sem
        # ela `motores_no_fisico` devolve `None` de propósito.
        rumble_no_fisico_ha_s=0.2,
        ff_ultimos_reports=[
            {"ha_s": 0.2, "weak": 255, "strong": 255, "ramo": "v1"}
        ],
    )

    valor = _valor(_painel_pintado(state), "vibracao")

    assert valor.get_text() == (
        f"{PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO]} (motores: 255/255)"
    )
    assert COR_DA_SITUACAO[SITUACAO_CHEGANDO] in valor.get_label()
