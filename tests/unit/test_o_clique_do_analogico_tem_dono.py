#!/usr/bin/env python3
"""A RÉGUA DO CLIQUE DO ANALÓGICO — e do terceiro estado que o produto não via.

POR QUE ELA EXISTE. `data-campo="l3"` e `data-campo="r3"` estão na página da aba
Controles desde o primeiro desenho, e até 02/09/2026 **ninguém os pintava**.
Medido pelo `casamento.medir("02-controles.html")` na ponta de `dev`
(2b219284): `vazios: ['l3', 'r3']` — a tela tinha onde e não havia quem
mandasse. Um endereço sem pintor não dá erro: `querySelector` acha o elemento,
o pacote não emite a chave, e o rótulo do mockup fica lá para sempre.

O QUE ELA COBRA, e o item 3 é o que dói:

1. os dois endereços recebem valor quando há leitura;
2. o clicado se distingue do solto;
3. **sem leitor, o valor é o travessão — nunca "solto".** `inputs` é `None`
   para todo controle que não seja o primário nem tenha retrato vivo do co-op
   (`daemon/ipc_handlers.py:2466-2470`), e foi assim que a mesa dela estava
   medida em 02/09/2026 às 04:23:

       uniq aabbcc000001 · bt  · is_primary True  · inputs presente · buttons []
       uniq aabbcc000002 · usb · is_primary False · inputs None

   Dizer "solto" sobre `None` é a tela afirmando uma leitura que ninguém fez —
   o mesmo defeito que `mesa_viva.SEM_LEITOR` nomeia: *"nunca o último valor
   como se fosse vivo, nunca zero fingindo repouso"*.

4. o mesmo para o touchpad, que era pior: `"touch-estado"` era a **constante**
   `"Sem toque"`. A tela afirmava, sem ler nada, que ninguém estava encostando.

5. e o espelho do item 1: **nada do que o pacote emite cai fora da página.**
   Eram três — `l2`, `r2` e `via` —, e os três entravam na conta de
   `cobertura.pintados` sem escrever um pixel.

A MORDIDA está escrita em cada teste, no lugar onde ela reprova.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"

#: O controle da régua. `is_primary` e `inputs` são o par que decide o terceiro
BASE = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "lightbar_rgb": [0, 0, 255], "is_primary": True,
    "audio": {}, "speaker": {},
}


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def desenho(a02):
    """O TEXTO DE TELA, e o dono dele é o PACOTE — não o gerador.

    A seta aponta para o produto por medição: o
    `portao_a_casa_sabe_e_o_produto_nao_faz` poda os `abaNN.py` da conta por
    serem BANCADA, e importar o gerador de dentro do pacote arrasta a bancada
    para o fecho de produção — em 02/09/2026 isso acendeu três lápides de
    `interface/monta.py` e reprovou o portão. Quem lê é o gerador.
    """
    return a02


def _card(pac, a02, entrada: dict) -> dict:
    """O dicionário de UM card, do pacote real, sem janela e sem daemon."""
    ctx = pac.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    return next(iter(a02.pacote(ctx)["cards"].values()))


def test_sem_apertar_o_rotulo_e_o_do_desenho(pac, a02, desenho):
    """Solto, o círculo mostra o rótulo que o gerador desenhou — e só ele."""
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]
    assert d["r3"] == desenho.ROTULO_DO_CLIQUE["r"]


@pytest.mark.parametrize(
    ("botao", "campo", "lado"),
    [("l3", "l3", "l"), ("r3", "r3", "r")],
)
def test_o_clique_de_cada_analogico_aparece_sozinho(
    pac, a02, desenho, botao, campo, lado
):
    """Clicar L3 marca L3 e **não** marca R3, e vice-versa."""
    d = _card(pac, a02, {**BASE, "inputs": {"buttons": [botao, "cross"]}})
    assert d[campo] == desenho.CLICADO % desenho.ROTULO_DO_CLIQUE[lado]
    outro = "r3" if campo == "l3" else "l3"
    outro_lado = "r" if lado == "l" else "l"
    assert d[outro] == desenho.ROTULO_DO_CLIQUE[outro_lado], (
        "o clique de um analógico acendeu o outro")


def test_sem_leitor_os_dois_analogicos_dao_travessao(pac, a02, desenho):
    """`inputs: None` é "não sei", e nunca "não apertado"."""
    import mesa_viva

    d = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert d["l3"] == mesa_viva.SEM_LEITOR
    assert d["r3"] == mesa_viva.SEM_LEITOR
    assert d["l3"] != desenho.ROTULO_DO_CLIQUE["l"], (
        "sem leitura, a tela mostrou o rótulo como se tivesse medido o repouso")


def test_dicionario_de_inputs_vazio_nao_e_falta_de_leitor(pac, a02, desenho):
    """`{}` é leitura que veio sem botão apertado — e isso é diferente de `None`."""
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]


#: 02/09/2026 às 19h, 60 leituras de `daemon.state_full` com os dois controles
#: `touchpad_do_inputs` nesta aba — e a recusa custou a POSIÇÃO do dedo.
TOUCHPAD_PUBLICADO = {
    "touching": False, "x": 960, "y": 540, "width": 1920, "height": 1080,
}


def test_o_touchpad_deixou_de_ser_constante(pac, a02):
    """"Sem toque" era literal no código: um dedo não mudava um pixel."""
    import mesa_viva
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    tocando = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": {**TOUCHPAD_PUBLICADO, "touching": True}}})
    solto = _card(pac, a02, {**BASE, "inputs": {"touchpad": TOUCHPAD_PUBLICADO}})
    cego = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert tocando["touch-estado"] == texto_toques(1) == "1 toque"
    assert solto["touch-estado"] == texto_toques(0) == "Sem toque"
    assert cego["touch-estado"] == mesa_viva.SEM_LEITOR


ESPERAM_A_PUBLICACAO: tuple[str, ...] = ()


def test_a_aba_controles_nao_emite_para_endereco_que_a_pagina_nao_tem():
    """Órfão é valor calculado a cada tique e jogado fora — e conta cobertura falsa."""
    import casamento

    m = casamento.medir("02-controles.html")
    orfaos = sorted(m["orfaos"])
    de_descuido = [k for k in orfaos if k not in ESPERAM_A_PUBLICACAO]
    assert de_descuido == [], (
        f"a aba Controles emite {de_descuido} e a página publicada não "
        f"tem endereço para eles — valor calculado a cada tique e jogado fora.")
    ainda_esperando = tuple(k for k in ESPERAM_A_PUBLICACAO if k in orfaos)
    assert ainda_esperando == ESPERAM_A_PUBLICACAO, (
        f"a declaração diz que {list(ESPERAM_A_PUBLICACAO)} esperam o "
        f"`--publicar`, e hoje só {list(ainda_esperando)} estão órfãos. Ou a "
        f"publicação aconteceu e a lista ficou para trás, ou ela foi escrita "
        f"antes da hora — nos dois casos a declaração parou de dizer a verdade.")


def test_a_aba_controles_nao_deixa_endereco_da_pagina_sem_pintor():
    """O outro lado do espelho: `vazios` era `['l3', 'r3']`."""
    import casamento

    m = casamento.medir("02-controles.html")
    import re as _re

    import monta

    do_piloto = set(_re.findall(r'data-campo="([^"]+)"', monta.fita([])))

    # (`aba02.py`, no `<input class="radio-mesa">`): os quatro rádios são um
    so_de_leitura = {
        "card-aberto": "grupo de rádio: pintar reabriria o card que ela fechou",
    }
    sobrando = sorted(set(m["vazios"]) - do_piloto - set(so_de_leitura))
    assert sobrando == [], (
        f"a página 02-controles.html tem {sobrando} e ninguém os "
        f"pinta — o rótulo do mockup fica na tela como se fosse leitura.")

    na_pagina = set(_re.findall(
        r'data-campo="([^"]+)"',
        (RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
        .read_text(encoding="utf-8")))
    mortas = sorted(set(so_de_leitura) - na_pagina)
    assert mortas == [], (
        f"{mortas} está declarado como só-de-leitura e não existe mais na "
        f"página — tire a declaração no mesmo commit que tirou o endereço")


def test_o_gerador_le_o_texto_de_tela_do_pacote(a02):
    """O `aba02.py` não pode ter uma SEGUNDA cópia das mesmas palavras."""
    import aba02
    from hefesto_dualsense4unix.app.widgets import sensor_widgets

    donos = {"ROTULO_DO_CLIQUE": a02, "CLICADO": a02, "texto_toques": sensor_widgets}
    achados = [n for n in donos if hasattr(aba02, n)]
    assert len(achados) >= 2, (
        f"o gerador só conhece {achados} — se ele parou de importar o texto de "
        f"tela do dono, esta régua ficou vazia e não mede mais nada.")
    for nome in achados:
        assert getattr(aba02, nome) is getattr(donos[nome], nome), (
            f"o gerador tem uma cópia própria de {nome} — duas verdades sobre "
            f"a mesma palavra de tela.")


def test_o_rotulo_do_circulo_e_o_mesmo_no_desenho_e_na_pintura(desenho):
    """A página publicada e o pacote têm de dizer a mesma palavra."""
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")
    for lado, campo in (("l", "l3"), ("r", "r3")):
        marca = f'data-campo="{campo}">{desenho.ROTULO_DO_CLIQUE[lado]}<'
        assert marca in html, (
            f"a página publicada não traz {marca!r} — o gerador e o pacote "
            f"passaram a dizer palavras diferentes sobre o mesmo círculo.")
