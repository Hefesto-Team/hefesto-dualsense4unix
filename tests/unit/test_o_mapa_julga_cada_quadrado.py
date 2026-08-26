"""Cada quadrado da janela do mapa diz se o aparelho fica bem ali.

LEVA 3, frente B (26/08/2026). A janela do mapa (``app/widgets/mapa_da_mesa.py``)
desenhava o gabinete e **cada quadrado ficava mudo**: ela importava
``censo_do_barramento``, ``i18n``, ``logging_config`` e ``utils.maquina``, e não
importava ``arranjo_da_mesa`` nem ``mapa_das_portas``. O motor que sabe
responder — 1.292 linhas portadas do mockup dela, com 114 testes de
equivalência contra o original em ``node`` — não tinha **uma única linha de
produção** que o chamasse. Era ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` na forma mais
cara: 37 das 87 lápides do portão eram deste motor.

O QUE ESTE ARQUIVO MEDE, E O QUE NÃO
-------------------------------------

Mede **a costura**: que o juízo do motor chega ao quadrado com a razão junto, e
que o desenho DELA é o que dispara a penalidade de vizinho rádio. Não mede as
regras do motor — quem faz isso é ``test_arranjo_invariantes.py`` (as duas
invariantes) e ``test_arranjo_da_mesa_bate_com_o_mockup.py`` (a equivalência com
o JavaScript), e os dois continuam verdes.

E mede a CONFISSÃO, que é metade da decisão dela: pela
``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS``, *"com o gabinete não desenhado o motor
fica sem par e as três penalidades de vizinho rádio não disparam, e a linha do
mapa passa a DIZER isso em vez de calar — juízo otimista silencioso é pior que
juízo nenhum"*. Um mapa que julgasse calando o que não sabe passaria neste
arquivo se ele só cobrasse o veredito; por isso o segundo teste cobra a frase.

A BANCADA É A DE MENTIRA, E ISSO NÃO É DETALHE
-----------------------------------------------

``test_mapa_a_bancada_de_mentira`` é o sysfs em memória de 25/08 às 02h30, e o
``mapa_dela()`` é o gabinete que ela desenhou. Medir contra a bancada de quem
roda o teste é a armadilha 1 do ``COMO-OLHAR-A-TELA.md`` entrando pela porta do
``/sys``. Nenhum aparelho é tocado, nenhum daemon é ouvido.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("o juízo de cada quadrado do mapa 2D")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
    CONFISSAO,
    CONFISSAO_ABERTURA,
    JanelaDoMapaDaMesa,
    LogicaDoMapa,
    bancada_do_rascunho,
)
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from tests.unit.test_mapa_a_bancada_de_mentira import (
    bancada_de_agora,
    mapa_dela,
)

#: O adaptador Bluetooth que está na ponta da extensão (entrada `15a`). É ele
#: que ela pega para colocar noutro lugar, e é o caso em que o vizinho importa.
BT_DA_EXTENSAO = "3-1.1.4"

#: A entrada em que o OUTRO adaptador Bluetooth (`3-1.1.1`) está declarado.
ENTRADA_DO_BT_DO_HUB = "13"

#: A entrada VAZIA que é irmã da `13` no desenho dela — a fileira do hub é lida
#: de duas em duas: 9-10, 11-12, 13-14, e a 15 sobra.
ENTRADA_COLADA_NO_BT = "14"


class _Hospedeiro:
    """O mínimo que a janela toca no hospedeiro — o rascunho e a marca."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcou = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcou += 1


def _janela(mapa: MapaDaMesa | None = None) -> JanelaDoMapaDaMesa:
    """A janela sobre a bancada de mentira, sem `show`.

    Ela NÃO é mostrada: sob Xvfb não há gerenciador de janelas e uma
    `Gtk.Window` mostrada fica 1x1 para sempre (`COMO-OLHAR-A-TELA.md`).
    """
    return JanelaDoMapaDaMesa(
        _Hospedeiro(),
        mapa_dela() if mapa is None else mapa,
        bancada_de_agora().censo(),
    )


def _rotulo(janela: JanelaDoMapaDaMesa, numero: str) -> str:
    return str(janela.quadrados[numero].get_label())


def _dica(janela: JanelaDoMapaDaMesa, numero: str) -> str:
    return str(janela.quadrados[numero].get_tooltip_text() or "")


# --- 1. O quadrado publica o veredito, e a razão junto ----------------------


def test_quadrado_com_veredito_ruim_nao_sai_verde() -> None:
    """Com um rádio na entrada colada, o quadrado vizinho reprova — e diz por quê.

    O caso é a mesa dela: a fileira do hub é lida de duas em duas, a `13` tem um
    adaptador Bluetooth e a `14` é a irmã dela **no metal**. Ela pega o outro
    adaptador; a `14` tem de dizer que ali não, e dizer que é por causa do que
    está na `13`.

    É o caminho inteiro numa asserção só: `irmas_de` (o desenho dela, de duas em
    duas) -> `Entrada.par` -> a penalidade de -45 do Bluetooth -> o veredito ->
    o rótulo e a dica do quadrado.
    """
    janela = _janela()
    janela.aparelhos[BT_DA_EXTENSAO].emit("clicked")

    veredito = janela.vereditos.get(ENTRADA_COLADA_NO_BT)
    assert veredito is not None, (
        f"com o adaptador {BT_DA_EXTENSAO} na mão, a entrada "
        f"{ENTRADA_COLADA_NO_BT} não publicou veredito nenhum — o quadrado "
        f"continua mudo. Vereditos publicados: {sorted(janela.vereditos)}"
    )
    assert veredito.v == "evite", (
        f"a entrada {ENTRADA_COLADA_NO_BT} está colada no Bluetooth da 13 e "
        f"saiu com o veredito {veredito.v!r} ({veredito.texto!r}) — juízo "
        "otimista onde deveria dizer 'aqui não'"
    )

    rotulo = _rotulo(janela, ENTRADA_COLADA_NO_BT)
    assert veredito.texto in rotulo, (
        f"o veredito {veredito.texto!r} não chegou ao rótulo do quadrado "
        f"{ENTRADA_COLADA_NO_BT}: {rotulo!r}"
    )
    dica = _dica(janela, ENTRADA_COLADA_NO_BT)
    assert veredito.porque and veredito.porque in dica, (
        f"a RAZÃO do veredito não chegou ao quadrado {ENTRADA_COLADA_NO_BT}. "
        f"O motor disse {veredito.porque!r}; a dica diz {dica!r}. Veredito sem "
        "razão é o conselho que a pessoa não entende, e por isso não segue"
    )
    assert ENTRADA_DO_BT_DO_HUB in veredito.porque, (
        "a razão não nomeia a entrada do vizinho, e sem o número dela a pessoa "
        f"não sabe o que tirar do caminho: {veredito.porque!r}"
    )


def test_o_par_sai_do_desenho_dela_e_nao_da_numeracao_do_kernel() -> None:
    """Trocar a ORDEM em que ela desenhou a fileira troca quem é vizinho de quem.

    É a prova de que o par vem de `irmas_de` (o desenho dela, de duas em duas) e
    não de alguma vizinhança do sysfs: com a `14` desenhada em par com a `15` em
    vez da `13`, o mesmo adaptador na mão deixa de ser vizinho do rádio, e o
    veredito da `14` muda de "vale evitar" para "melhor lugar".
    """
    bruto = mapa_dela().model_dump(mode="json")
    for face in bruto["faces"]:
        if face["nome"] == "Hub":
            face["portas"] = ["9", "10", "11", "12", "13", "14", "15"]
    de_pe = _janela(MapaDaMesa.model_validate(bruto))
    de_pe.aparelhos[BT_DA_EXTENSAO].emit("clicked")

    for face in bruto["faces"]:
        if face["nome"] == "Hub":
            # A `13` sai do par com a `14` e passa a fazer par com a `12`.
            face["portas"] = ["9", "10", "11", "13", "12", "14", "15"]
    trocado = _janela(MapaDaMesa.model_validate(bruto))
    trocado.aparelhos[BT_DA_EXTENSAO].emit("clicked")

    antes = de_pe.vereditos.get(ENTRADA_COLADA_NO_BT)
    depois = trocado.vereditos.get(ENTRADA_COLADA_NO_BT)
    assert antes is not None and depois is not None, (
        f"a entrada {ENTRADA_COLADA_NO_BT} ficou muda numa das duas ordens de "
        f"desenho (de pé: {antes}, trocado: {depois}) — o motor não está sendo "
        "chamado, e a comparação abaixo não teria o que medir"
    )
    assert antes.v == "evite" and depois.v != "evite", (
        "o veredito da entrada 14 não muda quando o DESENHO dela muda de "
        f"ordem ({antes.v!r} -> {depois.v!r}). Ou o par não está vindo de "
        "`irmas_de`, ou não está chegando ao motor — e nos dois casos as três "
        "penalidades de vizinho rádio (-30, -45, -40) estão desarmadas"
    )


# --- 2. O que o desenho não diz sai ESCRITO ---------------------------------


def test_sem_par_o_mapa_confessa() -> None:
    """`Entrada.pos` não tem fonte, e a janela DIZ isso em vez de calar.

    Decisão dela, `D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS`: *"a linha do mapa passa a
    DIZER isso em vez de calar — juízo otimista silencioso é pior que juízo
    nenhum"*.

    São dois fatos sem fonte na mesa dela, e a confissão nomeia os dois:

    * `Entrada.pos` — a posição do buraco na fileira do metal. Não existe no
      `MapaDaMesa`, não existe no censo, não existe no `/sys`. Sem ela o
      `_bonus_separacao` (+6 por posição de folga, teto 6) **nunca dispara**, e
      dois adaptadores nas pontas opostas do hub recebem o mesmo juízo de dois
      colados;
    * o par da entrada `15`, que sobra na fileira de sete do hub.
    """
    janela = _janela()

    assert janela.confissao, (
        "a janela não confessou nada, e a mesa dela tem pelo menos dois fatos "
        "sem fonte (a posição na fileira e o par da entrada 15). Silêncio aqui "
        "é o juízo otimista que a decisão dela mandou acabar"
    )
    frase_da_posicao = CONFISSAO[mapa_das_portas.LACUNA_POSICAO]
    assert frase_da_posicao in janela.confissao, (
        "a confissão não diz que ninguém declarou a posição de cada entrada na "
        f"fileira. O que ela diz: {janela.confissao}"
    )
    assert CONFISSAO[mapa_das_portas.LACUNA_PAR] in janela.confissao, (
        "a entrada 15 sobra na fileira de sete do hub e ficou sem irmã, e a "
        f"janela não disse isso: {janela.confissao}"
    )

    escritas = _todo_o_texto(janela)
    assert CONFISSAO_ABERTURA in escritas, (
        "a confissão existe no objeto e não chegou à tela — o cabeçalho dela "
        "não está em rótulo nenhum da janela"
    )
    assert frase_da_posicao in escritas, (
        "a frase da posição não chegou a rótulo nenhum da janela"
    )


def test_a_bancada_do_rascunho_responde_com_o_gabinete_vazio() -> None:
    """Quem nunca desenhou não recebe juízo nenhum, e também não recebe erro.

    Zero faces é estado legítimo e é como a janela nasce para quem nunca
    desenhou. A mesa sai vazia, e a confissão da POSIÇÃO cala: não há entrada
    sobre a qual mentir.
    """
    bancada = bancada_do_rascunho(LogicaDoMapa(MapaDaMesa()), bancada_de_agora().censo())

    assert bancada.mesa.faces == ()
    assert mapa_das_portas.LACUNA_POSICAO not in bancada.lacunas, (
        "sem face nenhuma não há fileira, e confessar a posição de entradas que "
        f"não existem é ruído: {bancada.lacunas}"
    )


# --- 3. O fato dela não se perde no caminho ---------------------------------


def test_o_rascunho_nao_derruba_o_que_so_ela_sabe_da_face() -> None:
    """`perto` e `alto` atravessam o rascunho — senão o "Aplicar" os apagaria.

    Os dois são FATO DELA (a face virada para quem senta, a face no alto do
    rack) e só ela os tem: o `/sys` desta bancada responde `panel=right` para as
    DUAS entradas da frente. A gravação SUBSTITUI a lista de faces inteira, então
    um rascunho que os deixasse cair apagaria do disco, no primeiro clique do
    desenho, o que ela declarou noutra tela.

    E não é só disco: são eles que ligam o bônus de +20 do teclado ("na frente,
    que é a mais perto de você") no motor.
    """
    bruto = mapa_dela().model_dump(mode="json")
    bruto["faces"][0]["perto"] = True
    bruto["faces"][2]["alto"] = True
    mapa = MapaDaMesa.model_validate(bruto)

    logica = LogicaDoMapa(mapa)
    logica.escolher("1-3")
    logica.colocar("3")
    documento = logica.como_documento()

    assert documento["faces"][0].get("perto") is True, (
        "a face que ela marcou como a mais perto voltou do rascunho sem o "
        f"fato dela: {documento['faces'][0]}"
    )
    assert documento["faces"][2].get("alto") is True, (
        "a face que ela marcou como a do alto voltou do rascunho sem o fato "
        f"dela: {documento['faces'][2]}"
    )
    bancada = bancada_do_rascunho(logica, bancada_de_agora().censo())
    assert bancada.mesa.faces[0].perto is True
    assert bancada.mesa.faces[2].alto is True


def _todo_o_texto(widget: Any) -> set[str]:
    """Todo rótulo da árvore de widgets, para conferir o que a tela DIZ."""
    achados: set[str] = set()
    pilha = [widget]
    while pilha:
        atual = pilha.pop()
        obter = getattr(atual, "get_text", None)
        if obter is not None and getattr(atual, "get_line_wrap", None) is not None:
            achados.add(str(obter()))
        filhos = getattr(atual, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados
