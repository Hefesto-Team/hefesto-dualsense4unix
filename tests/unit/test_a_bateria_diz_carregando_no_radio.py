#!/usr/bin/env python3
"""O ESTADO DE CARGA NÃO PERGUNTA POR ONDE O CONTROLE FALA — BATERIA-ICONE-01.

**A DECISÃO DELA, 06/09/2026, verbatim, e ela recusou as três opções que lhe
foram oferecidas:**

    *"icone mas no radio ele pode tá carregando
     tambem."*  <!-- noqa-acento: fala dela, verbatim -->

São DUAS coisas numa frase, e as duas viram régua aqui:

1. **a forma é ÍCONE**, não palavra — o card já tem o número, e a palavra ao
   lado custaria a largura que a linha fechada não tem. O ícone leva o nome no
   ``title``, para quem não reconhece o desenho;
2. **a premissa das opções estava errada.** As três foram escritas como se
   CARREGAR fosse coisa do cabo e o rádio fosse sempre descarregar. Não é: o
   transporte diz por onde o controle CONVERSA, a carga diz por onde entra
   ENERGIA, e um DualSense falando por rádio pode estar num cabo de energia.

**O QUE ESTA RÉGUA TRANCA, e é o motivo dela existir:** que ninguém, em nenhum
degrau do caminho, infira "carregando" de "cabo" nem "na bateria" de "rádio".
Ela anda o caminho inteiro com um controle **no rádio e carregando**:

    describe_controllers  →  carga_na_tela  →  pacote da aba 02  →  o HTML

**A MEDIÇÃO QUE ANTECEDEU A CURA (06/09/2026):** o acoplamento foi procurado de
propósito e **não existia no código** — o ``_detect_transport`` e o
``_read_battery_state_opt`` leem coisas diferentes, o ``ipc_handlers`` repassa o
dicionário verbatim, e a ``pydualsense`` corrige o offset do rádio antes de ler
o byte (``readInput``: ``states = inReport[1:]`` quando BT). O acoplamento
estava na PROSA — nas opções oferecidas a ela. Esta régua é o que impede que ele
desça da prosa para o código: hoje ela passa, e passa a reprovar no dia em que
alguém escrever o ``if transport == "usb"``.

AS MORDIDAS, e as quatro foram feitas antes de este arquivo ser commitado:

* faça ``carga_na_tela`` devolver ``""`` para quem não está no cabo —
  ``test_a_palavra_e_a_mesma_no_cabo_e_no_radio`` reprova;
* apague uma palavra de ``_NA_TELA_POR_CARGA`` —
  ``test_todo_estado_do_dono_tem_resposta_na_tela`` reprova nomeando o estado;
* tire o ``bateria-carga`` do pacote — ``test_o_card_do_radio_carregando_diz_o
  _icone`` reprova;
* tire o ``title`` do ícone no gerador — ``test_o_icone_tem_nome_acessivel``
  reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
import threading
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core.backend_pydualsense import (
    ESTADO_DE_CARGA,
    PyDualSenseController,
)
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
    carga_na_tela,
    estados_de_carga,
)

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

#: Um endereço da faixa forjada da casa — nunca o do aparelho dela.
UNIQ = "aa:bb:cc:00:00:02"
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]


def _handle(nibble: int, level: int, *, via: str) -> Any:
    """Um handle da pydualsense como o ``report_thread`` dela o deixa.

    ``via`` é o ``conType.name`` que o ``_detect_transport`` lê — e é o único
    lugar deste dublê que fala de transporte. A carga vem do ``battery``, que é
    outro objeto: eles não se tocam nem no dublê, que é o ponto.
    """
    return SimpleNamespace(
        battery=SimpleNamespace(Level=level, State=nibble),
        conType=SimpleNamespace(name=via),
        connected=True,
    )


def _backend(handle: Any) -> PyDualSenseController:
    backend = PyDualSenseController.__new__(PyDualSenseController)
    backend._handles = {"aabbcc000002": handle}
    backend._primary_key = "aabbcc000002"
    backend._io_lock = threading.RLock()
    return backend


def _entrada(**mais: Any) -> dict[str, Any]:
    base = {"uniq": UNIQ, "player": 1, "connected": True, "is_primary": True,
            "inputs": {}, "audio": {}, "speaker": {}, "battery_pct": 64}
    return {**base, **mais}


def _card(entrada: dict[str, Any]) -> dict[str, Any]:
    """O card que o pacote da aba 02 monta para esta entrada.

    **O `_ENDERECOS` É FORÇADO, E A RÉGUA DIZ POR QUÊ.** O pacote só emite os
    endereços da BANCADA quando a página PUBLICADA já os tem
    (`_so_se_a_pagina_tiver`) — e publicar é ato DELA, que ainda não olhou este
    desenho. Sem esta linha a régua mediria a espera pela publicação, não a
    cura: ela daria verde com o `bateria-carga` apagado no pacote.

    O que se força é só o CONJUNTO de endereços da página, nunca o valor: quem
    responde "Carregando" continua sendo o produto.
    """
    from pacotes import Contexto
    from pacotes import a02_controles as mod

    antes = mod._ENDERECOS
    try:
        mod._ENDERECOS = frozenset(mod._enderecos_da_pagina() | {"bateria-carga"})
        cards = mod.pacote(Contexto(state={"controllers": [entrada]},
                                    mesa=MESA, conectados=[entrada]))["cards"]
    finally:
        mod._ENDERECOS = antes
    assert len(cards) == 1, f"esperava um card, vieram {len(cards)}"
    return next(iter(cards.values()))


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. O DAEMON — dois fatos, duas leituras, nenhuma inferência
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("via", ["BT", "USB"])
def test_o_daemon_diz_carregando_nos_dois_transportes(via: str) -> None:
    """O MESMO byte de carga com o MESMO nibble, no cabo e no rádio.

    MORDE: faça `_carga` (ou `describe_controllers`) consultar o transporte
    antes de devolver `battery_state`, e o caso `BT` reprova.
    """
    entradas = _backend(_handle(0x1, level=65, via=via)).describe_controllers()
    assert entradas[0]["transport"] == ("bt" if via == "BT" else "usb")
    assert entradas[0]["battery_state"] == "carregando", (
        f"no transporte {via!r} o daemon devia dizer 'carregando' e disse "
        f"{entradas[0]['battery_state']!r} — o estado de carga é do BYTE, não "
        f"do transporte"
    )


def test_o_radio_nao_diz_so_carregando() -> None:
    """Não é só o carregando: os três estados comuns atravessam o rádio.

    Sem isto a régua acima passaria com um `if` que devolvesse "carregando"
    para tudo que fala por rádio — o acoplamento pelo lado avesso.
    """
    lidos = {
        nibble: _backend(_handle(nibble, level=65, via="BT"))
        .describe_controllers()[0]["battery_state"]
        for nibble in (0x0, 0x1, 0x2)
    }
    assert lidos == {0x0: "descarregando", 0x1: "carregando", 0x2: "cheio"}


# ---------------------------------------------------------------------------
# 2. A PALAVRA — lida do dono, e sem porta por onde o transporte entre
# ---------------------------------------------------------------------------


def test_todo_estado_do_dono_tem_resposta_na_tela() -> None:
    """A lista é a de `backend_pydualsense.ESTADO_DE_CARGA`, e não se digita.

    Um sexto estado que o kernel publique e a tela não conheça tem de REPROVAR
    aqui, nomeando-o — nunca sumir calado do card. É a regra da casa: quando um
    valor tem dono, a régua PERGUNTA ao dono.

    MORDE: apague uma linha de `_NA_TELA_POR_CARGA`.
    """
    from pacotes import a02_controles as mod

    assert estados_de_carga() == frozenset(ESTADO_DE_CARGA.values())
    sem_resposta = sorted(estados_de_carga() - set(mod._NA_TELA_POR_CARGA))
    assert not sem_resposta, (
        f"o daemon publica {sem_resposta} e a tela não sabe o que dizer sobre "
        f"esses estados — decida a palavra (ou o silêncio) em "
        f"`_NA_TELA_POR_CARGA`, nunca deixe cair no vazio por omissão"
    )


def test_carregando_e_cheio_tem_palavra_e_descarregando_e_silencio() -> None:
    """A decisão dela, lida ao pé da letra: só o que o número NÃO diz vira ícone.

    `descarregando` é o estado comum e o percentual ao lado já o conta; um ícone
    em todo card o tempo todo é ruído crônico.
    """
    assert carga_na_tela("carregando") == "Carregando"
    assert carga_na_tela("cheio") == "Cheio"
    assert carga_na_tela("descarregando") == ""


def test_fora_de_faixa_e_erro_falam_porque_o_numero_deixou_de_valer() -> None:
    """Os dois estados em que o driver ZERA a capacidade ganham palavra.

    O `hid-playstation` faz `capacity = 0` em `0xa`, `0xb` e `0xf`, enquanto a
    `pydualsense` segue calculando `nibble*10+5` do mesmo byte — o percentual
    que o card mostra nesses estados é um número que o driver já descartou.
    Calar ali seria a tela afirmando uma carga que ninguém sustenta.
    """
    assert carga_na_tela("fora_de_faixa") == "Fora de faixa"
    assert carga_na_tela("erro") == "Erro de carga"


def test_ninguem_reportou_ainda_nao_desenha_icone() -> None:
    """`None` e qualquer palavra que não seja do dono caem no silêncio.

    `""` é o que APAGA o atributo na pintura — inventar um ícone para "não sei"
    seria a tela afirmando o que ninguém mediu.
    """
    assert carga_na_tela(None) == ""
    assert carga_na_tela("plugado") == ""
    assert carga_na_tela(7) == ""


def test_a_funcao_da_palavra_nao_tem_por_onde_receber_o_transporte() -> None:
    """A decisão dela escrita na ASSINATURA, e é a régua mais barata do arquivo.

    Enquanto `carga_na_tela` receber só o estado, não há como acoplá-la ao
    transporte sem MUDAR A FORMA da função — e mudar a forma é o que esta régua
    nomeia.

    MORDE: acrescente um parâmetro `transport` e este caso reprova.
    """
    import inspect

    parametros = list(inspect.signature(carga_na_tela).parameters)
    assert parametros == ["estado"], (
        f"`carga_na_tela` passou a receber {parametros} — o estado de carga é "
        f"independente do transporte (decisão dela, 06/09/2026)"
    )


# ---------------------------------------------------------------------------
# 3. O CARD — o caminho inteiro, com o controle no rádio
# ---------------------------------------------------------------------------


def test_o_card_do_radio_carregando_diz_o_icone() -> None:
    """A cena da decisão dela, medida onde a tela lê: **rádio e carregando**.

    MORDE: tire o `"bateria-carga"` do pacote, ou faça-o consultar o
    `transport`, e este caso reprova.
    """
    card = _card(_entrada(transport="bt", battery_state="carregando"))
    assert card["bateria-carga"] == "Carregando", (
        "um controle NO RÁDIO e carregando não anunciou o estado no card — é "
        "exatamente a premissa que ela corrigiu: 'no radio ele pode tá "
        "carregando tambem'"  # noqa-acento: citação literal dela
    )


@pytest.mark.parametrize("estado", ["carregando", "cheio", "descarregando"])
def test_a_palavra_e_a_mesma_no_cabo_e_no_radio(estado: str) -> None:
    """O MESMO estado, os DOIS transportes, o MESMO valor no card.

    É a régua que fecha a porta pelos dois lados: nem "carregando" some no
    rádio, nem "descarregando" ganha ícone por estar no cabo.
    """
    no_cabo = _card(_entrada(transport="usb", battery_state=estado))
    no_radio = _card(_entrada(transport="bt", battery_state=estado))
    assert no_cabo["bateria-carga"] == no_radio["bateria-carga"] == carga_na_tela(estado)


def test_o_numero_e_o_estado_continuam_sendo_duas_coisas() -> None:
    """O ícone entrou SEM tocar no percentual, que tem dono próprio."""
    card = _card(_entrada(transport="bt", battery_pct=64, battery_state="carregando"))
    assert card["bateria"] == "64 %"
    assert card["bateria-barra"] == 64
    assert card["bateria-carga"] == "Carregando"


# ---------------------------------------------------------------------------
# 4. O HTML — o ícone existe, tem nome, e a cena ensina o caso dela
# ---------------------------------------------------------------------------


def _icones(doc: str) -> list[str]:
    return re.findall(r'<span class="carga"[^>]*>.*?</span></span>', doc, re.S)


def test_o_icone_tem_endereco_e_os_dois_alvos() -> None:
    """Dois elementos, um endereço só — a gramática do `giro-no-jogo`.

    O de fora veste o `title` (o nome), o de dentro veste o `data-carga` (a
    forma). Dois `data-campo` diferentes para o mesmo fato é o que esta casa
    persegue: eles poderiam DIVERGIR na tela.

    MORDE: tire um dos `data-hef-atributo` no gerador e regere a aba.
    """
    icones = _icones(_bancada())
    assert icones, "não achei o ícone de carga na bancada da aba Controles"
    for icone in icones:
        assert icone.count('data-campo="bateria-carga"') == 2
        assert 'data-hef-atributo="title"' in icone
        assert 'data-hef-atributo="data-carga"' in icone


def test_o_icone_tem_nome_acessivel() -> None:
    """A palavra vai no `title`, e é ela que um leitor de tela anuncia.

    Um ícone sem nome deixa quem não reconhece o desenho com o card de ontem —
    só o número. MORDE: apague o `title` em `selo_da_carga` e regere.
    """
    doc = _bancada()
    for palavra in (carga_na_tela("carregando"), carga_na_tela("cheio")):
        assert f'title="{palavra}"' in doc, (
            f"o ícone de {palavra!r} ficou sem nome acessível na bancada"
        )


def test_a_folha_casa_com_a_palavra_do_produto() -> None:
    """A regra de CSS é gerada da MESMA palavra que o produto escreve.

    Se a folha digitasse a palavra, a divergência seria SILENCIOSA — uma regra
    que não casa não dá erro, o ícone só sumiria da tela viva.
    """
    doc = _bancada()
    for estado in ("carregando", "cheio", "fora_de_faixa", "erro"):
        assert f'[data-carga="{carga_na_tela(estado)}"]' in doc, (
            f"a folha não tem regra para {carga_na_tela(estado)!r} — o ícone "
            f"desse estado não aparece na tela viva"
        )
    assert f'[data-carga="{carga_na_tela("descarregando")}"]' not in doc


def test_o_desenho_mostra_um_controle_no_radio_carregando() -> None:
    """A correção de premissa dela, virada CENA — é o que ela vai olhar.

    O mockup é o que ensina a ler o produto. Um desenho em que só o controle do
    cabo carrega ensinaria de volta a premissa errada.

    MORDE: troque o `carga` do P2 no `ESTADO` do gerador e regere a aba.
    """
    import aba02

    no_radio = [c for c in aba02.CONECTADOS if c.get("transporte") == "bt"]
    assert no_radio, "a cena do mockup ficou sem nenhum controle no rádio"
    assert any(aba02.ESTADO[c["pref"]].get("carga") == "carregando"
               for c in no_radio), (
        "nenhum controle no RÁDIO aparece carregando no desenho — a cena "
        "voltou a ensinar que carregar é coisa do cabo"
    )
