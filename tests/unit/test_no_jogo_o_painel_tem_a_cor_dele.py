"""NO-JOGO-SEM-FALSO-VERDE-01/T5 (a E2 da MESA-CHEIA-07) — a cor do painel.

**O defeito, medido:** com a mesa cheia, a aba "No jogo" desenhava QUATRO
molduras lilás idênticas na frente de quatro barras acesas em quatro cores.
O título de cada painel já era o mesmo do card (`titulo_do_card`); a cor
ficou para trás, e a única forma de saber de quem era cada moldura era ler o
número no título.

**A mordida principal é de IDENTIDADE, não de aparência** (MESA-CHEIA-07 §3,
mordida 1): para o mesmo ``entry``, a cor do painel tem de ser **byte a byte**
a mesma do card. Duas implementações divergem no primeiro caso de borda, e o
cabeçalho do módulo promete o contrário — *"Este módulo chama aquela função;
não reimplementa nem uma linha dela"*.

**Por que a cor CRUA e não a ajustada** (D8, e é o que separa `cor_do_swatch`
de `accent_do_card`): o quadradinho é a IDENTIDADE da cor. Um traço escuro
sobre fundo escuro some, e por isso o TRAÇO passa por `ensure_min_contrast`;
um quadrado preenchido com contorno neutro continua visível em qualquer cor, e
ajustá-lo faria as duas abas mostrarem cores diferentes para o mesmo controle.

**O que este teste NÃO prova:** que a cor é a que ela vê na barra. Isso é a
bancada dela — e, nesta aba, com o jogo aberto. A **D-1** (a cor do painel é a
VIVA da barra ou a da paleta COR-03?) continua sendo dela e continua aberta; o
que esta entrega faz é garantir que a resposta, qualquer que seja, valha para
as duas abas de uma vez, porque quem decide é uma função só.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("a cor do painel da aba No jogo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta — `gi` existe sem as
# typelibs no runner do CI, e o ImportError na COLETA derruba a suíte inteira.
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets import painel_no_jogo as pnj_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    LADO_DO_SWATCH,
    accent_do_card,
    cor_do_swatch,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import PainelNoJogo

_janelas_vivas: list[Any] = []

#: Roxo (128, 0, 255) — o caso de borda que a MESA-CHEIA-07 nomeou: escuro o
#: bastante para que a cor CRUA e a AJUSTADA sejam números diferentes.
_ROXO = (128, 0, 255)


def _entry(indice: int, rgb: Any, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "index": indice,
        "connected": True,
        "transport": "usb",
        "is_primary": indice == 0,
        "player": indice + 1,
        "player_slot": indice + 1,
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_rgb": list(rgb) if rgb is not None else None,
    }
    entry.update(extra)
    return entry


def _estado(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(e) for e in entries],
        "rumble_ff": {
            "per_vpad": [
                {"player": e["player"], "visto_ha_s": {"touchpad_click": 0.5}}
                for e in entries
            ]
        },
    }


def _painel(entry: dict[str, Any], state: dict[str, Any]) -> PainelNoJogo:
    painel = PainelNoJogo()
    janela = Gtk.OffscreenWindow()
    janela.add(painel)
    janela.show_all()
    _janelas_vivas.append(janela)
    painel.atualizar(entry, state)
    return painel


# ---------------------------------------------------------------------------
# A mordida 1 — identidade, byte a byte
# ---------------------------------------------------------------------------


def test_a_cor_do_painel_e_a_mesma_do_card_byte_a_byte() -> None:
    """A asserção é de identidade, e é a razão de a função ser importada.

    Arranque para ver reprovar: escrever uma leitura de cor própria dentro de
    `painel_no_jogo.py` (por exemplo, `tuple(entry["lightbar_rgb"])` inline) em
    vez de chamar `cor_do_swatch`. Enquanto o payload for bem formado as duas
    coincidem; no primeiro caso de borda — canal fora de 0..255, lista de dois
    elementos, valor em texto — elas divergem, e o quadradinho do mesmo
    controle passa a ter uma cor em cada aba.
    """
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb == cor_do_swatch(entry)
    assert painel._swatch_rgb == _ROXO


def test_o_swatch_mostra_a_cor_crua_e_nao_a_ajustada() -> None:
    """D8 em uma asserção: o quadradinho é identidade, o traço é legibilidade.

    O roxo (128, 0, 255) existe neste arquivo por isto: `accent_do_card` o
    devolve CLAREADO para garantir o piso de contraste do traço. Se o painel
    passasse a cor pelo ajuste, ele mostraria um roxo que a barra não tem — e
    diferente do quadradinho do card, que é o mesmo elemento.
    """
    entry = _entry(0, _ROXO)
    state = _estado([entry])

    painel = _painel(entry, state)

    assert accent_do_card(entry, state) != _ROXO, (
        "o caso de borda perdeu a graça: escolha uma cor cujo ajuste de "
        "contraste mude os bytes, senão esta régua não distingue as duas"
    )
    assert painel._swatch_rgb == _ROXO


@pytest.mark.parametrize(
    "bruto",
    [
        pytest.param([1, 2], id="dois-canais"),
        pytest.param([0, 0, 0, 0], id="quatro-canais"),
        pytest.param(["ff", 0, 0], id="canal-em-texto"),
        pytest.param({"r": 1, "g": 2, "b": 3}, id="dicionario"),
        pytest.param("azul", id="nome-da-cor"),
    ],
)
def test_o_payload_torto_cai_no_mesmo_lugar_nas_duas_abas(bruto: Any) -> None:
    """O primeiro caso de borda — é aqui que uma cópia diverge, não no feliz.

    Uma leitura ingênua (`tuple(entry["lightbar_rgb"])`) devolve `(1, 2)` para
    uma lista de dois canais e ESTOURA num dicionário; `cor_do_swatch` devolve
    `None` nos cinco, porque fora do contrato do IPC "cor desconhecida" é a
    única resposta honesta. Um payload torto não é hipótese de laboratório: é o
    daemon mais velho que o código, que nesta casa é rotina.

    Arranque para ver reprovar: a mesma da mordida 1 — trocar `cor_do_swatch`
    por uma leitura própria dentro do painel.
    """
    entry = _entry(0, None)
    entry["lightbar_rgb"] = bruto

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb == cor_do_swatch(entry)
    assert painel._swatch_rgb is None


def test_o_painel_nao_tem_leitura_de_cor_propria() -> None:
    """A contraprova estrutural da mordida 1, no fonte.

    Identidade de resultado passaria também com uma cópia bem-comportada da
    função. O que o cabeçalho do módulo promete é mais forte — *"não
    reimplementa nem uma linha dela"* —, e é isto que esta régua mede: o painel
    não lê `lightbar_rgb` do payload, ele pergunta a quem é dono.
    """
    texto = Path(pnj_mod.__file__).read_text(encoding="utf-8")

    assert "lightbar_rgb" not in texto
    assert "cor_do_swatch" in texto


# ---------------------------------------------------------------------------
# O painel de CADA controle recebe a cor DELE
# ---------------------------------------------------------------------------


def test_quatro_controles_quatro_cores() -> None:
    """O defeito inteiro, na forma em que ele aparece: a mesa cheia.

    Arranque para ver reprovar: passar sempre o mesmo `entry` ao `atualizar` —
    é a família do defeito que a T4 da Onda 3 curou nos cards, em que três das
    quatro posições recebiam o registro do vizinho.
    """
    entries = [
        _entry(0, (0, 0, 255)),
        _entry(1, (255, 0, 0)),
        _entry(2, (0, 255, 0)),
        _entry(3, (255, 0, 128)),
    ]
    state = _estado(entries)

    cores = [_painel(e, state)._swatch_rgb for e in entries]

    assert cores == [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 0, 128)]
    assert len(set(cores)) == 4


def test_sem_cor_conhecida_o_quadradinho_fica_vazio() -> None:
    """Sem leitura da lightbar, ``None`` — e o desenho vira só o contorno.

    É a mesma regra da tela inteira desta aba: onde não há dado, ela CALA em
    vez de escrever zero. Um preto preenchido diria "a barra está apagada", que
    é uma afirmação diferente de "ninguém leu a barra".
    """
    entry = _entry(0, None)

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb is None


# ---------------------------------------------------------------------------
# O diff, que é onde uma cor nova costuma congelar
# ---------------------------------------------------------------------------


def test_trocar_so_a_cor_repinta_o_quadradinho() -> None:
    """A metade que se esquece: a cor tem de estar na ASSINATURA do diff.

    Arranque para ver reprovar: tirar `cor_do_controle` da tupla `assinatura`
    de `atualizar`. O painel volta cedo — título, recado e linhas continuam
    iguais —, e o quadradinho fica com a cor da primeira pintura para sempre.
    Ela troca a cor na aba Início, volta para cá, e vê a cor velha.
    """
    entry = _entry(0, (0, 0, 255))
    painel = _painel(entry, _estado([entry]))
    assert painel._swatch_rgb == (0, 0, 255)

    novo = _entry(0, (255, 0, 0))
    painel.atualizar(novo, _estado([novo]))

    assert painel._swatch_rgb == (255, 0, 0)


def test_o_titulo_continua_o_mesmo_do_card() -> None:
    """O cabeçalho virou um `Gtk.Box`, e o título tinha de sobreviver a isso.

    Trocar `set_label` por um `label_widget` é a mudança estrutural desta
    entrega, e ela tem uma forma clássica de dar errado: o rótulo fica no
    widget novo e ninguém o alimenta mais. Aqui o texto é lido do widget de
    verdade, e comparado com a função-dona do título.
    """
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    assert painel._titulo_label.get_text() == pnj_mod.titulo_do_painel(entry)
    assert painel._titulo_label.get_text() != ""


def test_o_quadradinho_tem_o_mesmo_lado_do_card() -> None:
    """Mesmo elemento, mesmo tamanho — e o número tem um dono só."""
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    largura, altura = painel._swatch.get_size_request()
    assert (largura, altura) == (LADO_DO_SWATCH, LADO_DO_SWATCH)
