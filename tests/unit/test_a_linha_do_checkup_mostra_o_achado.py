#!/usr/bin/env python3
"""A LINHA DO CHECK-UP MOSTRA O ACHADO — e não o nome de quem o procurou.

**04/10/2026:** a linha do exame saiu da aba Conexões (cada achado virou um cartão de dica,
AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01). O que fica aqui é o dado da linha (`_linha`, o selo e a dica
do dono), que a aba Jogar ainda lê pelo `_exame()`; as réguas dos endereços da página
saíram com ela.

**02/09/2026.** As cinco linhas do Check-up da aba Conexões têm três partes: o
selo, a frase e o `?`. A frase e o selo já vinham do exame da bancada; as
TRÊS estavam erradas, cada uma de um jeito, e as três têm dono no produto.

**A FRASE MOSTRAVA O RÓTULO.** O pacote emitia ``[i["titulo"] for i in itens]``
— o ``Item.rotulo``, que é o NOME da conferência. Fotografado nesta bancada,
com dois controles na mesa::

    CERTO  Economia de energia desligada        ← o nome do exame
    CERTO  Energia das portas                   ← o nome do exame
    CERTO  Suporte ao controle                  ← o nome do exame

onde o desenho dela promete um achado. A regra é do produto e está escrita no
pacote da aba (``interface/pacotes/a08_conexoes.py``, na chave ``achado``):
*"O texto é o ``porque`` — a MEDIÇÃO em uma frase —, nunca o rótulo: a tela
aprovada mostra o que se achou, não o nome do que se conferiu."* Os mesmos três
itens, pelo ``porque``::

    O sistema está proibido de desligar o rádio dos controles.
    Conferido agora: nenhuma das 16 portas USB está em economia de energia.
    A parte do sistema que fala com o DualSense está carregada.

**O SELO PERDIA UMA PALAVRA.** Ele saía de ``"AJUSTAR" if grave else "CERTO"``,
e o ``Item`` tem QUATRO estados. ``interface.conexoes.SELO_DO_ESTADO`` os mapeia
em TRÊS palavras, e a que sumia era a **NOTA** do ``nao_sei`` — a mesma que o
desenho dela crava na quarta linha. Um "não deu para olhar" chegava à tela como
"AJUSTAR": a tela afirmando um problema que ninguém mediu.

**O `?` NÃO TINHA ENDEREÇO.** Ele continuava sendo o do MOCKUP enquanto o selo
e a frase ao lado já eram os dela — a linha 1 dizia "Economia de energia
desligada" e o `?` explicava *"as entradas em uso entregam 500 mA ou mais"*, que
é a medição de OUTRO achado.

**E ENTÃO O `?` PASSOU A REPETIR A LINHA — decisão, 02/09/2026.** Com a
publicação do mesmo dia a linha passou a mostrar a MEDIÇÃO, e a dica ao lado
trazia essa mesma medição na segunda das três metades: a pessoa lia a frase e
a lia de novo ao parar o ponteiro. O `?` fica com o que a linha NÃO diz — **por
que aquilo importa** e **o que fazer**.

A montagem continua sendo do produto (``DICAS_DAS_LINHAS`` e
``PREFIXO_DA_CURA``, de ``secao_exame``); o que mudou é QUEM PEDE. O dono
``_dica_do_item`` fica intacto porque a janela GTK também o usa, e **lá a linha
mostra o ``rotulo``** (``secao_exame.PainelDoExame``, ``:1177``) — naquela tela
a dica é o único caminho de ``Item.porque`` até a pessoa. Duas telas mostram
coisas diferentes na linha, logo pedem dicas diferentes.

**O QUARTO SELO — decisão, 02/09/2026.** ``SELO_DO_ESTADO`` manda
``atencao`` e ``problema`` para a MESMA palavra e a MESMA pílula  (noqa-acento)
laranja, e o usuário
decidiu que *"o que está quebrado agora não pode parecer igual ao que só podia
estar melhor"*. Esta leva entrega a **cor**: a pílula ganhou o endereço
``selo-estado`` (alvo ``classe``), o pacote emite o ESTADO cru e o desenho traz
``.selo.grave`` em ``var(--red)``. **A PALAVRA continua sendo "AJUSTAR" e é
espera dela** — trocá-la seria escolher no lugar dela.

**A MORDIDA:** troque ``i["porque"]`` por ``i["titulo"]`` na chave ``achado`` do
pacote, devolva o selo binário, tire o ``data-campo="achado-explica"`` do
gerador, ponha o ``porque`` de volta na dica, ou apague o ``selo-estado`` —
todos reprovam, cada um com a sua frase.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

PACOTE = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
BANCADA = RAIZ / "mockup/08-conexoes.html"


def _item(**troca):
    """Um `Item` do exame de mentira, com os campos que a tela lê."""
    base = {
        "chave": "energia_das_portas",
        "rotulo": "Energia das portas",
        "estado": "certo",
        "porque": "Conferido agora: nenhuma das 16 portas USB está em economia de energia.",
        "cura": None,
    }
    base.update(troca)
    return Item(**base)


def test_a_frase_da_linha_e_a_medicao_e_nao_o_rotulo():
    """O que vai para `data-campo="achado"` é o `porque` do `Item`."""
    it = _item()
    linha = a08._linha(it)
    assert linha["porque"] == it.porque
    assert linha["titulo"] == it.rotulo
    assert linha["porque"] != linha["titulo"]


@pytest.mark.parametrize(
    ("estado", "palavra", "classe"),
    [
        ("certo", "CERTO", "ok"),
        ("atencao", "AJUSTAR", "warn"),  # (noqa-acento) chave de máquina
        ("problema", "AJUSTAR", "warn"),
        ("nao_sei", "NOTA", "info"),
    ],
)
def test_o_selo_sai_do_mapa_do_produto(estado, palavra, classe):
    """Os quatro estados do `Item` viram as três palavras do desenho dela."""
    linha = a08._linha(_item(estado=estado))
    assert linha["selo"] == palavra
    assert linha["classe"] == classe


def test_o_nao_sei_nao_vira_um_alarme():
    """A regressão que o selo binário produzia, nomeada."""
    assert a08._linha(_item(estado="nao_sei"))["selo"] != "AJUSTAR"


def test_um_estado_que_a_tela_nao_conhece_nao_vira_verde():
    """Reserva do dono: o desconhecido é NOTA, que é a palavra que não afirma."""
    linha = a08._linha(_item(estado="um_estado_que_ninguem_escreveu"))
    assert linha["selo"] == "NOTA"
    assert linha["classe"] == "info"


# --- o QUARTO selo: `problema` deixa de parecer `atencao` ---  # (noqa-acento): nome de estado


def test_o_problema_e_o_atencao_chegam_a_tela_como_estados_diferentes():
    """A cor sai do ESTADO, e é ele que separa os dois — não a palavra.

    Enquanto o único canal era `SELO_DO_ESTADO`, os dois estados chegavam à
    tela como a mesma pílula laranja e a mesma palavra: *"o que está quebrado
    agora parecia igual ao que só podia estar melhor"*, que é a frase de produto.
    """
    quebrado = a08._linha(_item(estado="problema"))
    so_podia_melhorar = a08._linha(_item(estado="atencao"))  # (noqa-acento) id
    assert quebrado["estado"] != so_podia_melhorar["estado"], (
        "o pacote parou de distinguir `problema` de `atencao` no que manda "  # (noqa-acento) chave
        "para a tela — sem isso a cor do quarto selo não tem em que se apoiar"
    )
    assert quebrado["selo"] == so_podia_melhorar["selo"] == "AJUSTAR"


def test_a_dica_da_linha_traz_as_duas_metades_do_produto():
    """O `?` traz o "por que importa" e a cura — as duas frases do produto."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import (
        DICAS_DAS_LINHAS,
        PREFIXO_DA_CURA,
    )

    it = _item(estado="atencao", cura="Troque o cabo de entrada.")  # (noqa-acento): nome de estado
    dica = a08._linha(it)["dica"]
    assert DICAS_DAS_LINHAS["energia_das_portas"] in dica
    assert PREFIXO_DA_CURA + it.cura in dica


def test_a_dica_nao_repete_a_medicao_que_a_linha_ja_mostra():
    """Decisão, 02/09/2026 — e é a metade do meio que sai."""
    it = _item(estado="atencao", cura="Troque o cabo de entrada.")  # (noqa-acento) id
    linha = a08._linha(it)
    assert linha["porque"] == it.porque, "a linha continua mostrando a medição"
    assert it.porque not in linha["dica"], (
        "o `?` da linha voltou a repetir a medição que a linha ao lado já "
        "mostra — decisão dela de 02/09/2026"
    )


def test_a_dica_quebra_linha_em_html_e_nao_em_texto():
    """O alvo é `html`: `\\n\\n` não quebra nada num `<span>`."""
    dica = a08._linha(_item(cura="Faça isto."))["dica"]
    assert "<br><br>" in dica
    assert "\n" not in dica


def test_a_dica_escapa_o_que_viesse_do_exame():
    """Alvo `html` sem escape é marcação vinda do sistema entrando na tela."""
    dica = a08._linha(_item(cura="use a & b < c"))["dica"]
    assert "&amp;" in dica
    assert "&lt;" in dica


def test_uma_linha_sem_cura_nao_inventa_o_que_fazer():
    """`cura=None` é o caso normal do `certo` — e não vira uma frase vazia."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA

    assert PREFIXO_DA_CURA not in a08._linha(_item())["dica"]


def test_o_carimbo_e_a_contagem_sairam_do_canto_da_gestao():
    """26/09/2026, pedido: *«vamos remover essas infos que aparecem no"""
    html = BANCADA.read_text(encoding="utf-8")
    assert 'data-campo="examinado"' not in html
    assert 'data-campo="conta-gestao"' not in html
    for texto in (html, GERADOR.read_text(encoding="utf-8")):
        inicio = texto.index('for="cx8-2">Gestão de Controles</label>')
        topo = texto[inicio:texto.index('class="quadro-corpo"', inicio)]
        assert 'class="conta"' not in topo, topo
    pacote = PACOTE.read_text(encoding="utf-8")
    assert '"examinado":' not in pacote and '"conta-gestao":' not in pacote
    assert not hasattr(a08, "_carimbo_do_exame")


@pytest.mark.parametrize(
    "entrada",
    ["aa:bb:cc:00:00:22", "AA-BB-CC-00-00-22", "  aabbcc000022  ", "aabbcc000022", ""],
)
def test_a_chave_do_maquina_json_e_a_do_produto(entrada):
    """`_so_hex` é embrulho de `core.sysfs_leds.norm_mac`, e não a segunda conta."""
    assert a08._so_hex(entrada) == (norm_mac(entrada) or "")


def test_o_so_hex_nunca_devolve_none():
    """`norm_mac` devolve `None` sem um hexa sequer; aqui isso tem de virar `""`."""
    assert norm_mac("zzz") is None
    assert a08._so_hex("zzz") == ""


def test_nao_sobrou_uma_segunda_conta_de_normalizacao_neste_arquivo():
    """A cópia à mão (`.replace(":", "").replace("-", "")`) não pode voltar."""
    fonte = PACOTE.read_text(encoding="utf-8")
    corpo = fonte.split("def _so_hex", 1)[1].split("\ndef ", 1)[0]
    assert 'replace(":", "")' not in corpo, (
        "o `_so_hex` desta aba voltou a normalizar por conta própria — a chave "
        "do `maquina.json` tem um dono só, `core.sysfs_leds.norm_mac`"
    )


def test_o_dataclass_do_exame_ainda_tem_os_campos_que_a_tela_le():
    """Se o `Item` mudar de forma, a tela some sem uma linha de erro."""
    campos = {c.name for c in dataclasses.fields(Item)}
    assert {"chave", "rotulo", "estado", "porque", "cura"} <= campos
