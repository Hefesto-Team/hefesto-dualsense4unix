#!/usr/bin/env python3
"""A LEITURA VIVA DA ABA 02 DEIXA DE SER DESENHO — 03/09/2026.

A aba Controles é a aba da leitura ao vivo: os dezesseis glifos, os dois
analógicos, os gatilhos, o giroscópio e o acelerômetro. **Nada disso tinha
endereço.** O que estava na tela dela eram os valores que o gerador cravou uma
vez, e a medição de 03/09 os pôs lado a lado com o que o daemon publicava no
mesmo instante, com o aparelho PARADO na mesa:

    na tela (o desenho)              no aparelho (`daemon.state_full`)
    cross · dpad_up · l2 acesos      buttons = []
    L2 200 / 255 · R2 40 / 255       l2_raw = 0 · r2_raw = 0
    giro +143.2 / -412.0 / +22.8     gyro  x=-0.24 y=-0.61 z=-0.3
    accel +0.105 / +0.976 / +0.170   accel x=0.116 y=0.948 z=0.204
    X:  60 · Y: 200                  lx=125 ly=121

**NÃO É TELA VAZIA, É TELA QUE MENTE** — e no card do P2 é pior: ele não tem
`inputs` nenhum (o daemon só publica leitura para o `is_primary`) e mostrava os
mesmos números, como se estivesse medindo.

POR QUE UM ARQUIVO ALÉM DO `casamento` E DA RÉGUA DO MOCKUP, e as duas são
cegas a isto por CONSTRUÇÃO: o `casamento.medir` compara o que o pacote emite
com os `data-campo` da página, e fechava PERFEITO — zero órfãos, zero vazios —
justamente porque nem um lado nem o outro tinha estes endereços. A régua do
mockup conta `data-campo` e dava `23 campos · 23 PRODUTO · 0 MOCKUP`. As duas
mediam o que existe; nenhuma mede o que a GTK faz e o HTML não.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/02-controles.html"

#: MACs da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ_CABO = "aa:bb:cc:00:00:01"
UNIQ_RADIO = "aa:bb:cc:00:00:02"

#: OS DOIS CONTROLES DA MESA DELA, na forma do `state_full` medido em
#: 03/09/2026: um `is_primary` COM leitura e um por rádio SEM `inputs` nenhum.
#: O segundo é metade da mesa dela e é o card que mais mentia.
CABO = {
    "uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 95, "player_slot": 1,
    "vpad_backend": "uhid",
    "inputs": {
        "buttons": ["cross", "r1"], "l2_raw": 200, "r2_raw": 12,
        "lx": 125, "ly": 121, "rx": 128, "ry": 125,
        "gyro": {"x": -0.24, "y": -412.0, "z": 0.0},
        "accel": {"x": 0.116, "y": 0.948, "z": 0.204},
    },
}
SEM_LEITURA = {
    "uniq": UNIQ_RADIO, "transport": "bt", "battery_pct": 15, "player_slot": 2,
    "vpad_backend": "uhid",
}

MESA = [
    {"pref": "p1", "uniq": UNIQ_CABO, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": UNIQ_RADIO, "jogador": 2, "cor": "",
     "nome": "Não sei", "via": "BT", "transporte": "bt", "alvo": False,
     "mascara": "DualSense"},
]

#: OS 46 ENDEREÇOS QUE A LEITURA VIVA PRECISA, montados pela mesma regra que os
#: escreve — e não digitados. Uma lista à mão aqui seria a segunda cópia da
#: gramática, e ela envelheceria calada no dia em que um eixo mudasse de nome.
GLIFOS = [
    "cross", "circle", "square", "triangle",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "l1", "r1", "l2", "r2",
    "share", "options", "ps", "touchpad",
]
EIXOS = [
    f"{fam}-{e}{suf}"
    for fam in ("giro", "accel")
    for e in ("x", "y", "z")
    for suf in ("", "-neg", "-pos", "-cor")
]
DA_LEITURA_VIVA = (
    [f"glifo-{n}" for n in GLIFOS]
    + ["l2-num", "l2-barra", "r2-num", "r2-barra", "xy-l", "xy-r"]
    + EIXOS
)


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture()
def ctx(a02):
    """O `Contexto` da mesa dela, com a BANCADA como lista de endereços válidos.

    POR QUE A BANCADA E NÃO O PUBLICADO: `_so_se_a_pagina_tiver` pergunta à
    página PUBLICADA, e **publicar é ato dela**. Perguntar ao publicado hoje
    faria este arquivo passar por VACUIDADE — o pacote não emitiria nenhum dos
    46 e não haveria o que conferir. É o mesmo desvio que
    `test_aba02_a_identidade_vem_da_fita` já usa, pela mesma razão.
    """
    from pacotes import Contexto

    a02._ENDERECOS = frozenset(
        re.findall(r'data-campo="([^"]+)"', BANCADA.read_text(encoding="utf-8")))
    yield Contexto(state={}, mesa=MESA, conectados=[CABO, SEM_LEITURA], estados={})
    a02._ENDERECOS = None


# ---------------------------------------------------------------------------
# 1. O DESENHO TEM ONDE O PRODUTO ESCREVER
# ---------------------------------------------------------------------------
def test_a_bancada_tem_os_quarenta_e_seis_enderecos_da_leitura_viva():
    """Sem eles a pintura escreve zero, calada — e foi o estado até hoje."""
    doc = BANCADA.read_text(encoding="utf-8")
    faltam = [c for c in DA_LEITURA_VIVA if doc.count(f'data-campo="{c}"') != 2]
    assert not faltam, f"{len(faltam)} endereço(s) não estão nos DOIS cards: {faltam[:8]}"


def test_o_glifo_e_a_barra_declaram_o_alvo_que_o_piloto_precisa():
    """Alvo errado escreve o valor DENTRO do elemento em vez de acender/medir.

    Um glifo sem `data-hef-alvo="classe"` receberia o texto `sim` por cima do
    SVG; uma barra sem `largura` receberia o número dentro da barrinha. Os dois
    são falhas mudas — o `escrever` do piloto não reclama de nada.
    """
    doc = BANCADA.read_text(encoding="utf-8")
    for campo, alvo in (
        ("glifo-cross", "classe"), ("l2-barra", "largura"),
        ("giro-x-neg", "largura"), ("giro-x-pos", "largura"),
        ("giro-x-cor", "cor"), ("xy-l", "html"),
    ):
        assert re.search(
            rf'data-campo="{campo}"\s+data-hef-alvo="{alvo}"', doc
        ), f"`{campo}` não declara `data-hef-alvo=\"{alvo}\"`"


# ---------------------------------------------------------------------------
# 2. O PRODUTO ESCREVE — e escreve o que LEU
# ---------------------------------------------------------------------------
def test_os_glifos_acendem_os_apertados_e_apagam_o_resto(a02):
    """Os dezesseis, um a um. No desenho três ficam acesos para sempre."""
    v = a02.leitura_viva(CABO)
    acesos = {n for n in GLIFOS if v[f"glifo-{n}"]}
    # `l2` entra porque 200 passa do limiar do produto (`L2_R2_THRESHOLD` = 30);
    # `r2` fica fora porque 12 não passa. É a mesma conta do `_refresh_glyphs`.
    assert acesos == {"cross", "r1", "l2"}


def test_o_limiar_de_l2_e_o_do_produto_e_nao_um_maior_que_zero(a02):
    """`> 0` acenderia o glifo com o dedo apenas encostado no gatilho."""
    from hefesto_dualsense4unix.app.widgets.controller_card import L2_R2_THRESHOLD

    entrada = {"inputs": {"buttons": [], "l2_raw": L2_R2_THRESHOLD}}
    assert a02.leitura_viva(entrada)["glifo-l2"] == ""
    entrada["inputs"]["l2_raw"] = L2_R2_THRESHOLD + 1
    assert a02.leitura_viva(entrada)["glifo-l2"]


def test_o_share_acende_com_o_nome_que_o_daemon_publica(a02):
    """BUG-GLYPH-SHARE-NAME-MISMATCH-01: o daemon manda `create`, o glifo é `share`."""
    v = a02.leitura_viva({"inputs": {"buttons": ["create"]}})
    assert v["glifo-share"], "o glifo do `share` fica morto sem o remendo do nome"


def test_os_gatilhos_dizem_a_frase_da_gtk_e_a_barra_acompanha(a02):
    v = a02.leitura_viva(CABO)
    assert v["l2-num"] == "200 / 255"
    assert v["r2-num"] == "12 / 255"
    assert v["l2-barra"] == 200 * 100 // 255
    assert v["r2-barra"] == 12 * 100 // 255


def test_os_analogicos_usam_a_frase_do_produto(a02):
    """`_markup_xy` é o dono, e o `<br>` é a quebra que a tela dela usa."""
    from hefesto_dualsense4unix.app.widgets.controller_card import _markup_xy

    v = a02.leitura_viva(CABO)
    assert v["xy-l"] == _markup_xy(125, 121).replace("\n", "<br>")
    assert v["xy-r"] == _markup_xy(128, 125).replace("\n", "<br>")


def test_o_zero_do_analogico_e_o_extremo_e_nao_o_centro(a02):
    """O `or 128` transformaria o talo à esquerda no repouso — erro de 128.

    É o defeito que `mesa_viva._eixo_do_analogico` mediu e curou em 29/08, e
    ele é alcançável na mesa dela: o `absinfo` dos dois DualSense dá `min=0`.
    """
    v = a02.leitura_viva({"inputs": {"lx": 0, "ly": 0}})
    assert v["xy-l"].startswith("X:  0"), v["xy-l"]


def test_os_sensores_usam_a_grafia_de_largura_fixa_da_gtk(a02):
    """Sete caracteres, `+7.1f` no giro e `+7.2f` no g — o painel não respira."""
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_eixo, texto_eixo_g

    v = a02.leitura_viva(CABO)
    assert v["giro-y"] == texto_eixo(-412.0)
    assert v["accel-y"] == texto_eixo_g(0.948)


def test_a_barra_negativa_cresce_para_a_esquerda_e_a_positiva_para_a_direita(a02):
    """As duas metades são exclusivas: uma tem largura, a outra tem zero.

    É o que faz o par `right:50%` / `left:50%` desenhar os mesmos pixels que o
    `left:L%;width:W%` de um elemento só — e é a única forma de a barra andar
    com o alvo `largura`, que é o que o piloto tem.
    """
    v = a02.leitura_viva(CABO)
    assert float(v["giro-y-neg"]) > 0 and v["giro-y-pos"] == "0"
    assert v["accel-y-neg"] == "0" and float(v["accel-y-pos"]) > 0


def test_a_cor_da_barra_sai_do_dono_e_nao_daqui(a02):
    """Verde para positivo, vermelho para negativo, cinza para o repouso."""
    import mesa_viva

    v = a02.leitura_viva(CABO)
    assert v["giro-y-cor"] == "var(--red)"
    assert v["accel-y-cor"] == "var(--green)"
    # O giro em Z é ZERO: a barra não afirma direção nenhuma.
    assert v["giro-z-cor"] == mesa_viva._barra_bipolar(0.0, 500.0)["background"]


# ---------------------------------------------------------------------------
# 3. SEM LEITOR, NADA DE NÚMERO — o card que mais mentia
# ---------------------------------------------------------------------------
def test_sem_leitor_tudo_volta_ao_repouso_e_nao_ao_desenho(a02):
    """O `_reset_inputs_render` da GTK, linha por linha.

    Vale para METADE da mesa dela agora: o daemon só publica `inputs` para o
    `is_primary`, e o card do outro mostrava três glifos acesos, L2 em 200/255
    e seis eixos com número.
    """
    v = a02.leitura_viva(SEM_LEITURA)
    assert not [n for n in GLIFOS if v[f"glifo-{n}"]], "um glifo ficou aceso sem leitor"
    assert v["l2-num"] == "0 / 255" and v["l2-barra"] == 0
    assert v["r2-num"] == "0 / 255" and v["r2-barra"] == 0
    assert v["xy-l"].endswith("Y:128") and v["xy-r"].endswith("Y:128")
    for campo in EIXOS:
        if campo.endswith(("-neg", "-pos")):
            assert v[campo] == "0", f"{campo} afirma uma barra sem leitura"
        elif not campo.endswith("-cor"):
            assert v[campo] == "—", f"{campo} mostra número sem leitura"


def test_o_sensor_ausente_e_diferente_do_sensor_em_zero(a02):
    """`gyro` que não veio é travessão; `gyro` em zero é `+0.0`.

    Os leitores de sensor nascem sob demanda (`sensor_hub.leitura`), então o
    bloco some e volta com o controle ligado. Zero fingindo repouso é o que
    `gyro_do_inputs` existe para não deixar acontecer.
    """
    ausente = a02.leitura_viva({"inputs": {"buttons": []}})
    em_zero = a02.leitura_viva({"inputs": {"gyro": {"x": 0.0, "y": 0.0, "z": 0.0}}})
    assert ausente["giro-x"] == "—"
    assert em_zero["giro-x"].strip() == "+0.0"


# ---------------------------------------------------------------------------
# 4. O PACOTE LEVA OS 46 À TELA
# ---------------------------------------------------------------------------
def test_o_pacote_emite_os_quarenta_e_seis_para_os_dois_cards(a02, ctx):
    p = a02.pacote(ctx)
    for uniq in (UNIQ_CABO, UNIQ_RADIO):
        faltam = [c for c in DA_LEITURA_VIVA if c not in p["cards"][uniq]]
        assert not faltam, f"{uniq}: {len(faltam)} campo(s) não emitidos: {faltam[:8]}"


def test_o_pacote_nao_inventa_endereco_que_a_pagina_nao_tem(a02, ctx):
    """A outra metade da régua: emitir a mais é órfão no `casamento`, e mentira
    na conta de `cobertura.pintados` — o pacote se reportaria pintando o que não
    pinta. É o defeito que custou 13 relatados para 10 pintados em 01/09/2026."""
    tem = a02._enderecos_da_pagina()
    p = a02.pacote(ctx)
    sobrando = [c for c in p["cards"][UNIQ_CABO] if c not in tem]
    assert not sobrando, f"emitiu para endereço que a página não tem: {sobrando}"


def test_a_conta_de_cobertura_inclui_a_leitura_viva(a02, ctx):
    """O contador é O instrumento com que esta casa prova que um endereço existe."""
    p = a02.pacote(ctx)
    assert p["cobertura"]["pintados"] == sum(len(v) for v in p["cards"].values()) + len(
        p["mesa"])
    assert p["cobertura"]["pintados"] >= 2 * len(DA_LEITURA_VIVA)


# ---------------------------------------------------------------------------
# 5. O GERADOR VOLTA A RODAR — e a bancada é reproduzível
# ---------------------------------------------------------------------------
def test_a_ancora_do_plastico_acha_os_chips_da_fita_de_hoje():
    """`monta.fita()` pôs `data-campo="fita-chip"` ENTRE o `class` e o `style`.

    Com a âncora exigindo os dois vizinhos, `python3 aba02.py` morria com
    `ERRO no plástico: 2 caixa(s) e 0 chip(s)` — e `monta()` GRAVA antes deste
    pós-processamento, então quem rodasse o gerador ficava com a bancada dela
    meio pronta no disco. A régua olha a FORMA de hoje, não o número.
    """
    import aba02
    from monta import fita

    # A MESA DO MOCKUP, e não a de cima: os dois controles dela têm cor lida,
    # que é a condição para `monta.fita()` escrever o `style="--plastico:…"`.
    # Com um controle por rádio (cor não lida) o chip nasce SEM estilo — e uma
    # régua montada sobre ele acharia um chip só e chamaria isso de forma
    # quebrada. É o número de `CONECTADOS` que a âncora do gerador cobra.
    clicavel = aba02.fita_clicavel(fita(ativo="p1"))
    achados = aba02.CHIP_COM_COR.findall(clicavel)
    assert len(achados) == len(aba02.CONECTADOS), (
        f"a âncora do plástico achou {len(achados)} chip(s) na fita de hoje")
