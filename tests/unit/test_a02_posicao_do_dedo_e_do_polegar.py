#!/usr/bin/env python3
"""A POSIÇÃO DO PONTINHO — a queixa dela, e a régua que ela deixa.

A QUEIXA É DELA, 04/09/2026, com dois DualSense na mesa (um no cabo, um no
rádio, os dois validados): *"não funciona o touch, analogicos"*.

E ela estava certa nos dois. O DADO CHEGAVA INTEIRO — `daemon/sensor_hub.py`
publica o bloco `touchpad` com as cinco chaves juntas (`touching`, `x`, `y`,
`width`, `height`) e o `inputs` com `lx`/`ly`/`rx`/`ry` — e morria no
`style=` de linha do desenho, que o produto não alcançava.

A PRIMEIRA CURA (04/09) foi uma folha endereçada, `posicao-css`, trocada
inteira a cada tique. Ela moveu os pontinhos e repintava a janela toda dez vezes
por segundo: 37,7% de um núcleo no WebKit, medido na banca em 25/09/2026.

A CURA DE HOJE (A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01) é o alvo `posicao`:
cada pontinho tem um endereço, o produto escreve `--hef-x`/`--hef-y` nele, e a
página tem UMA regra com o repouso como reserva do `var()`. O exemplo do
desenho vai cravado no próprio pontinho.

O QUE ESTA RÉGUA MEDE, e o que cada teste MORDE está escrito no teste:

1. **o dado chega ao endereço** — com touchpad e analógicos sintéticos, o
   pacote emite `x,y` lidos, e `""` onde não leu;
2. **a página não tem posição fora do alvo** — nenhum `style="left:…%;top:…%"`,
   nenhuma folha `posicao-css`, a regra única e os quatro endereços por lugar;
3. **o desenho continua no desenho** — o P1 do mockup mostra, lido pela régua
   do mockup, o exemplo que o desenho cravou.

O QUE ELA NÃO MEDE: o WebKit calculando o `left`. Isso é da régua no tempo
(`test_a_janela_aberta_nao_gasta_o_processador.py`, R5), que abre o piloto.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O TOUCHPAD COMO O DAEMON O PUBLICA, com o dedo em três quartos da largura e
#: um quarto da altura. Os limites são os que o payload declara.
DEDO = {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080}

#: OS DOIS POLEGARES, e o esquerdo está no TALO — `lx=0` é o extremo à
#: esquerda, não o centro (o defeito que `mesa_viva._eixo_do_analogico` curou em
#: 29/08/2026).
POLEGARES = {"lx": 0, "ly": 255, "rx": 128, "ry": 128}


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def pagina() -> str:
    """A página da BANCADA — o desenho de hoje, que é o que ela olha."""
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina("02-controles.html").read_text(encoding="utf-8")


BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
}
MESA = [{"uniq": UNIQ, "pref": "p1", "nome": "White", "via": "USB", "cor": "white"}]


def _posicoes(pac, a02, entrada: dict, monkeypatch) -> dict[str, str]:
    """Os quatro endereços de posição que o pacote emite para UM controle.

    O `_ENDERECOS` É FORÇADO, e a razão é de calendário: `_so_se_a_pagina_tiver`
    pergunta à página **publicada**, e os endereços nascem na BANCADA. Sem este
    desvio esta régua mediria a data da publicação, e não a cura.
    """
    monkeypatch.setattr(
        a02, "_ENDERECOS", frozenset(a02.CAMPOS_DA_POSICAO.values()), raising=False)
    ctx = pac.Contexto(state={}, mesa=MESA, conectados=[entrada], estados={})
    card = a02.pacote(ctx)["cards"][UNIQ]
    return {alvo: card[campo] for alvo, campo in a02.CAMPOS_DA_POSICAO.items()}


# --------------------------------------------------------------------------
# 1. O DADO CHEGA AO ENDEREÇO
# --------------------------------------------------------------------------
def test_a_posicao_do_dedo_chega_ao_endereco(pac, a02, monkeypatch):
    """Com o dedo em 75%/25% do pad, o endereço do dedo diz `75.0,25.0`.

    MORDE: devolver `None` no lugar da posição em `dedos_do_controle` apaga o
    valor, e o pontinho iria ao repouso com o dedo no pad.
    """
    pos = _posicoes(pac, a02, {**BASE, "inputs": {"touchpad": DEDO}}, monkeypatch)
    assert pos["touch"] == "75.0,25.0", f"a posição do dedo não chegou: {pos}"
    assert pos["touch2"] == "", (
        f"o pacote escreveu posição para um segundo dedo que não está lá: {pos}")


def test_o_segundo_dedo_tem_endereco_proprio(pac, a02, monkeypatch):
    """MULTITOQUE-01: dois dedos no pad, dois endereços — distintos.

    MORDE: apontar os dois alvos para o mesmo `data-campo` em
    `CAMPOS_DA_POSICAO` faz o segundo sobrescrever o primeiro.
    """
    dois = {**DEDO, "pontos": [{"slot": 0, "x": 1440, "y": 270, "id": 7},
                               {"slot": 1, "x": 480, "y": 810, "id": 8}]}
    pos = _posicoes(pac, a02, {**BASE, "inputs": {"touchpad": dois}}, monkeypatch)
    assert (pos["touch"], pos["touch2"]) == ("75.0,25.0", "25.0,75.0"), pos
    assert len(set(a02.CAMPOS_DA_POSICAO.values())) == len(a02.CAMPOS_DA_POSICAO)


def test_a_posicao_dos_polegares_chega_ao_endereco(pac, a02, monkeypatch):
    """Os dois analógicos, e o esquerdo no TALO: `lx=0` é 0%, não o centro.

    MORDE: ler o eixo com `inputs.get("lx") or 128` — o defeito de 29/08 —
    põe `50.2` no lugar do `0.0`.
    """
    pos = _posicoes(pac, a02, {**BASE, "inputs": dict(POLEGARES)}, monkeypatch)
    assert pos["ana-e"] == "0.0,100.0", f"o polegar esquerdo: {pos}"
    assert pos["ana-d"] == "50.2,50.2", f"o polegar direito: {pos}"


def test_sem_leitura_nenhum_pontinho_tem_posicao(pac, a02, monkeypatch):
    """O controle sem `inputs` não afirma posição: os quatro saem vazios.

    É o card do P2 da mesa dela quando o daemon só publica `inputs` para o
    primário. O vazio tira `--hef-x`/`--hef-y` e o pontinho cai no repouso.

    MORDE: emitir a posição sem leitor (trocar o `if tem_leitor` por `True` em
    `posicoes_do_controle`) põe `50.2,50.2` nos analógicos.
    """
    pos = _posicoes(pac, a02, {**BASE, "inputs": None}, monkeypatch)
    assert pos == dict.fromkeys(a02.CAMPOS_DA_POSICAO, ""), pos


def test_o_repouso_e_a_reserva_da_regra(a02):
    """A regra única lê as duas variáveis, e o repouso do analógico é a reserva."""
    assert a02.REPOUSO_DA_POSICAO == 50.2
    assert a02.REGRA_DAS_POSICOES == (
        ".ctl .touch .ponto,.ctl .stick .p"
        "{left:var(--hef-x,50.2%);top:var(--hef-y,50.2%)}")
    assert a02.texto_da_posicao(None) == ""
    assert a02.texto_da_posicao((0.0, 100.0)) == "0.0,100.0"


def test_a_folha_trocada_a_cada_tique_nao_volta(a02):
    """O pacote não emite mais a folha `posicao-css` nem a monta.

    MORDE: devolver `"posicao-css": folha_das_posicoes(...)` ao `pacote()`.
    """
    assert not hasattr(a02, "folha_das_posicoes")
    fonte = pathlib.Path(a02.__file__).read_text(encoding="utf-8")
    assert '"posicao-css":' not in fonte


# --------------------------------------------------------------------------
# 2. A PÁGINA NÃO TEM POSIÇÃO FORA DO ALVO
# --------------------------------------------------------------------------
def test_a_pagina_nao_tem_posicao_no_style_de_linha(pagina):
    """Nenhum `style="left:…%;top:…%"` sobrou — estilo de linha vence tudo."""
    achados = re.findall(r'style="left:[0-9.]+%;top:[0-9.]+%"', pagina)
    assert not achados, achados[:3]


def test_a_pagina_nao_tem_a_folha_e_tem_a_regra_unica(pagina, a02):
    """Sem `posicao-css`, e com a regra que lê as duas variáveis, uma vez.

    MORDE: devolver o `posicao_por_regra` ao `__main__` do gerador põe a folha
    de volta; tirar a regra do `CSS` do gerador a apaga.
    """
    assert 'data-campo="posicao-css"' not in pagina
    assert pagina.count(a02.REGRA_DAS_POSICOES) == 1


def test_cada_lugar_tem_os_quatro_enderecos(pagina, a02):
    """Quatro pontinhos por lugar, os quatro com o alvo `posicao`.

    O lugar vazio também tem, sem exemplo: é o que faz o cartão vazio virar um
    cartão de verdade no instante em que o controle chega.
    """
    lugares = len(re.findall(r'<div class="ctl card[^"]*" data-controle="p\d"', pagina))
    assert lugares == 4, f"a régua achou {lugares} lugares — régua que acha zero é ERRO"
    for campo in a02.CAMPOS_DA_POSICAO.values():
        assert pagina.count(f'data-campo="{campo}" data-hef-alvo="posicao"') == lugares, campo


# --------------------------------------------------------------------------
# 3. O DESENHO CONTINUA NO DESENHO
# --------------------------------------------------------------------------
def test_o_p1_do_mockup_mostra_o_exemplo_do_desenho(pagina):
    """Lido pela RÉGUA DO MOCKUP, o P1 está onde o desenho o pôs.

    O exemplo é o mesmo da folha de antes: os polegares em 23,5/78,4 e
    70,6/35,3, os dedos em 62/44 e 38/56. E o lugar vazio não tem nenhum.

    MORDE DUAS VEZES: tirar o `onde_esta` do `bloco()` manda o P1 ao centro
    (os quatro saem vazios); tirar o ramo `posicao` de `regua_do_mockup._campo`
    faz a régua ler o texto do `<span>`, vazio, nos quatro.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup

    do_p = {(c.dono, c.chave): c for c in regua_do_mockup._campos_cravados(pagina)
            if c.alvo == "posicao"}
    esperado = {"pos-ana-e": "23.5,78.4", "pos-ana-d": "70.6,35.3",
                "pos-touch": "62,44", "pos-touch-2": "38,56"}
    lido = {chave: do_p[("p1", chave)].valor for chave in esperado}
    assert lido == esperado, f"o P1 do mockup saiu do desenho: {lido}"
    assert all(do_p[("p3", chave)].valor == "" for chave in esperado), (
        "o lugar vazio ganhou exemplo de posição")


def test_a_regua_fala_a_lingua_do_alvo(pagina):
    """O travessão do lugar vazio é o repouso, que a tela lê vazio."""
    from hefesto_dualsense4unix.interface import regua_do_mockup

    campo = next(c for c in regua_do_mockup._campos_cravados(pagina)
                 if c.alvo == "posicao")
    assert regua_do_mockup._declarado_neste_elemento(
        campo, regua_do_mockup.TRAVESSAO) == ""
    assert regua_do_mockup._declarado_neste_elemento(campo, "0.0,100.0") == "0.0,100.0"
    assert regua_do_mockup._posicao_do_estilo("--hef-x:62.0%;--hef-y:44%") == "62.0,44"
