"""O card de ordem responde — e a dispensa dela é sobre um FATO, não uma palavra.

O QUE ESTE ARQUIVO TRAVA
-------------------------

Até 26/08/2026 a seção do exame tinha **um** botão ("Examinar de novo"): ela lia
a ordem de serviço, ia lá, movia o aparelho, e não tinha como dizer isso ao
produto. A lógica inteira já estava escrita e medida em
`integrations/ordens_da_mesa.py` — `resposta_ao_ja_movi`, `ordens_novas`,
`ordens_caladas`, `cabecalho`, `identidades` — e não tinha um único chamador de
produção. Era a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma cara: cinco funções
medidas e nenhuma tela.

A MORDIDA é a `D-ORDEM-IGNORADA-VOLTA`, e ela é uma frase dela: *"a chave do
dispensado é o ARRANJO, não a recomendação"*. Ela mexeu nos cabos, o conselho
pode ter mudado, e um conselho dispensado sobre um arranjo que não existe mais
não é o mesmo conselho. Filtrar pelo slug faria a decisão de ontem calar uma
medição de hoje — e o defeito seria MUDO: a ordem simplesmente nunca mais
apareceria, sem erro, sem log, sem nada na tela.

A segunda é a `D-O-QUE-O-PRODUTO-DIZ-SEM-SABER` aplicada ao topo: zero ordens
com alguma checagem que **não soube** é cinza, nunca verde — e a frase do topo
tem de dizer que alguma coisa não deu resposta, em vez de "Nada a mudar".

POR QUE ``Gtk.OffscreenWindow``, E NUNCA ``Gtk.Window``
--------------------------------------------------------

Sob Xvfb não há gerenciador de janelas, e uma ``Gtk.Window`` fica 1x1 para
sempre: os filhos nunca ganham tamanho e o teste passa a medir o servidor X em
vez do produto. É a armadilha nº 2 de `docs/process/COMO-OLHAR-A-TELA.md`.

NADA AQUI TOCA A MÁQUINA
-------------------------

Os `Item` e as `Ordem` são construídos à mão. Nenhuma função deste arquivo abre
`/sys`, lê o `maquina.json` ou fala com o rádio: o hospedeiro é um dublê com um
`_maquina_pendente` e mais nada, que é exatamente a superfície que a seção usa
para acumular a decisão dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`. `importorskip("gi")`
# aceita o stub que outro arquivo planta em `sys.modules`; esta guarda não.
exigir_gi_real("os dois botões do card de ordem")

import time
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_exame as secao
from hefesto_dualsense4unix.integrations import exame_da_mesa as exame_mod
from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens

#: O arranjo da bancada de 24/08: o aparelho de 5 Gbps e o dongle que o acusou.
#: Caminho de barramento, e nada mais — nunca serial, nunca endereço.
ARRANJO_DE_ANTES = "4-1.1.2|3-1.1.4"

#: O mesmo par depois de ela mudar o cabo de lugar.
ARRANJO_DE_DEPOIS = "4-1.1.2|3-1.2"


class HospedeiroDeMentira:
    """O que a seção precisa do `HefestoApp`, e nada além.

    Um dublê que só sabe passar não é dublê: `_marcar_declaracao_por_aplicar`
    conta as chamadas, porque a decisão dela tem de acender a marca do rodapé —
    sem isso ela declara, clica no X e nunca vê o aviso de que há coisa por
    aplicar (defeito medido em 23/08/2026).
    """

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcou = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcou += 1


def uma_ordem(
    *,
    chave: str = ordens.R1_RADIO_LARGO_NO_MESMO_HUB,
    arranjo: str = ARRANJO_DE_ANTES,
    acao: str = "Mova o aparelho de 5 Gbps para uma entrada do computador",
) -> ordens.Ordem:
    """Uma ordem completa — as três linhas, o alvo e o arranjo."""
    return ordens.Ordem(
        chave=chave,
        acao=acao,
        o_que_eu_vi=ordens.Linha(
            texto="O aparelho divide o hub com um adaptador",
            selo=ordens.MEDIDO_AQUI,
        ),
        por_que_importa=ordens.Linha(
            texto="Rádio largo colado a rádio estreito atrapalha",
            selo=ordens.MEDIDO_AQUI,
        ),
        ganho_esperado=ordens.Linha(
            texto=ordens.NAO_MEDI, selo=ordens.DERIVADO_DA_CONTA
        ),
        alvo=ordens.Identidade(vid="2357", pid="012d", caminho="4-1.1.2"),
        arranjo=arranjo,
        destino="4",
    )


def item_da_ordem(ordem: ordens.Ordem) -> exame_mod.Item:
    """A ordem embrulhada como o exame a entrega à tela."""
    return exame_mod.Item(
        chave=ordem.chave,
        rotulo=exame_mod.ROTULO_DA_ORDEM,
        estado=exame_mod.ESTADO_ATENCAO,
        porque=ordem.o_que_eu_vi.texto,
        cura=ordem.acao or None,
        ordem=ordem,
    )


def conferencia(
    chave: str, estado: str, *, cura: str | None = None
) -> exame_mod.Item:
    """Uma das cinco linhas da tira — nunca uma ordem."""
    return exame_mod.Item(
        chave=chave,
        rotulo=chave,
        estado=estado,
        porque="o que o exame achou",
        cura=cura,
    )


#: As cinco conferências todas respondendo "certo". É o pano de fundo neutro:
#: qualquer cor no topo destes testes veio das ordens, não da tira.
CINCO_CERTAS = [
    conferencia(chave, exame_mod.ESTADO_CERTO)
    for chave, _rotulo in secao.PainelDoExame._linhas_do_desenho()
]


def montar() -> tuple[Gtk.OffscreenWindow, secao.PainelDoExame, HospedeiroDeMentira]:
    """O painel de PRODUÇÃO, montado numa janela que existe de verdade."""
    hospedeiro = HospedeiroDeMentira()
    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    janela.add(caixa)
    painel = secao.PainelDoExame(hospedeiro)
    painel.montar(caixa)
    janela.show_all()
    return janela, painel, hospedeiro


def aplicar(painel: secao.PainelDoExame, itens: list[exame_mod.Item]) -> None:
    """Uma rodada de exame, com a dispensa que a seção já tem em mãos.

    `dispensadas=None` preserva o que a seção guardou — é o que o worker faz
    quando o disco não mudou, e é o que permite ao teste medir a decisão dela
    sobrevivendo a um exame novo.
    """
    painel.aplicar(itens, exame_mod.veredito(itens), time.time())


def arvore(raiz: Any) -> list[Any]:
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def textos(raiz: Any) -> list[str]:
    """O texto de todo `Gtk.Label` da árvore — e **nenhum tooltip**.

    A omissão é o ponto: nada aqui lê `get_tooltip_text()`, então tudo que estas
    asserções encontram chegou à tela por um caminho que a pessoa vê sem passar
    o mouse por cima de nada.
    """
    return [
        widget.get_text()
        for widget in arvore(raiz)
        if isinstance(widget, Gtk.Label) and widget.get_text()
    ]


def botao(raiz: Any, rotulo: str) -> Any:
    """O primeiro `Gtk.Button` com este rótulo, ou `None`."""
    for widget in arvore(raiz):
        if isinstance(widget, Gtk.Button) and widget.get_label() == rotulo:
            return widget
    return None


# ---------------------------------------------------------------------------
# 1. A MORDIDA: a dispensa é sobre o ARRANJO, e a ordem volta quando ele muda.
# ---------------------------------------------------------------------------


def test_ordem_ignorada_reaparece_quando_o_arranjo_muda() -> None:
    """`D-ORDEM-IGNORADA-VOLTA` — a chave do dispensado é o ARRANJO.

    Três passagens sobre a MESMA regra:

    1. a ordem nasce e o card traz os dois botões;
    2. ela aperta "Ignorar" — o card some, e some **de novo** no exame seguinte
       com o mesmo arranjo: a decisão dela sobrevive ao reexame;
    3. ela mexe nos cabos, a mesma regra dispara com arranjo NOVO — e a ordem
       **volta**.

    Chavear a dispensa só pelo slug faz a passagem 3 falhar, e falhar em
    silêncio: a ordem nunca mais apareceria, sem erro e sem log.
    """
    janela, painel, _hospedeiro = montar()
    antes = uma_ordem(arranjo=ARRANJO_DE_ANTES)

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(antes)])
    assert antes.acao in " ".join(textos(janela)), (
        "a ordem não chegou à tela antes de ela dispensar nada"
    )

    ignorar = botao(painel.cards, secao.ROTULO_IGNORAR)
    assert ignorar is not None, (
        "o card de ordem nasceu sem o botão "
        f"{secao.ROTULO_IGNORAR!r} — ela não tem como dispensar o conselho"
    )
    ignorar.clicked()
    assert antes.acao not in " ".join(textos(janela)), (
        "ela apertou Ignorar e o card ficou: a dispensa não chegou à tela"
    )

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(antes)])
    assert antes.acao not in " ".join(textos(janela)), (
        "a ordem voltou num exame em que NADA mudou — a decisão dela não "
        f"sobreviveu ao reexame (arranjo {ARRANJO_DE_ANTES!r} nas duas rodadas)"
    )

    depois = uma_ordem(arranjo=ARRANJO_DE_DEPOIS)
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(depois)])

    assert depois.acao in " ".join(textos(janela)), (
        "a mesma regra voltou a disparar com um arranjo NOVO e a ordem "
        "continuou calada — a dispensa foi chaveada pela recomendação em vez "
        "de pelo arranjo, e a decisão de ontem calou uma medição de hoje.\n"
        f"  arranjo dispensado: {ARRANJO_DE_ANTES!r}\n"
        f"  arranjo de agora:   {ARRANJO_DE_DEPOIS!r}\n"
        f"  o que a seção guardou: {painel._dispensadas!r}"
    )


def test_a_dispensa_desce_ao_rascunho_com_a_data_e_o_arranjo() -> None:
    """O que ela dispensou tem de chegar ao disco — pelo "Aplicar" do rodapé.

    Sem o arranjo gravado junto, o `maquina.json` de amanhã não tem como saber
    para QUAL mesa a decisão valia, e a ordem nunca mais volta. Sem a marca do
    rodapé, ela dispensa, clica no X e nunca vê que havia coisa por aplicar.
    """
    _janela, painel, hospedeiro = montar()
    ordem = uma_ordem(arranjo=ARRANJO_DE_ANTES)

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])
    botao(painel.cards, secao.ROTULO_IGNORAR).clicked()

    pendente = hospedeiro._maquina_pendente
    assert pendente is not None, "a dispensa não foi parar em rascunho nenhum"
    gravada = pendente["mesa"]["ordens_dispensadas"][ordem.chave]
    assert gravada["arranjo"] == ARRANJO_DE_ANTES
    assert gravada["quando"], "a dispensa desceu sem data"
    assert hospedeiro.marcou >= 1, (
        "o rodapé não soube que há declaração por aplicar"
    )


def test_a_dispensa_de_uma_regra_nao_cala_a_outra() -> None:
    """Duas ordens na tela, uma dispensada: a outra fica."""
    janela, painel, _hospedeiro = montar()
    primeira = uma_ordem(acao="Mova o aparelho de 5 Gbps")
    segunda = uma_ordem(
        chave=ordens.R4_TECLADO_SO_NO_HUB,
        arranjo="3-1.4",
        acao="Mova o teclado para o computador",
    )

    aplicar(
        painel,
        [*CINCO_CERTAS, item_da_ordem(primeira), item_da_ordem(segunda)],
    )
    cards = painel.cards.get_children()
    assert len(cards) == 2, f"esperava dois cards de ordem, vieram {len(cards)}"
    # O botão do PRIMEIRO card, e não "o primeiro botão que a varredura achar":
    # a árvore é percorrida em pilha, e qual dos dois vem antes é acidente de
    # travessia. Uma dispensa cega ao card mediria a ordem errada.
    botao(cards[0], secao.ROTULO_IGNORAR).clicked()

    juntos = " ".join(textos(janela))
    assert primeira.acao not in juntos
    assert segunda.acao in juntos, (
        "dispensar uma ordem calou a outra: a dispensa deixou de ser por regra"
    )


def test_o_ver_do_cabecalho_revela_a_ordem_calada() -> None:
    """Dispensa que some sem deixar marca é o card que some, de novo.

    Ela precisa saber que existe uma decisão dela ali — o cabeçalho conta, e o
    `[Ver]` mostra. O card revelado vem SEM os dois botões: um conselho que ela
    já mandou calar não tem o que confirmar nem o que dispensar de novo.
    """
    janela, painel, _hospedeiro = montar()
    ordem = uma_ordem()

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])
    botao(painel.cards, secao.ROTULO_IGNORAR).clicked()

    ver = botao(janela, ordens.cabecalho(
        ordens=[], conferidas=5, sem_resposta=0, dispensadas=1
    ).botao)
    assert ver is not None, "o cabeçalho contou a dispensa e não ofereceu o Ver"
    ver.clicked()

    assert ordem.acao in " ".join(textos(janela))
    assert botao(painel.cards, secao.ROTULO_IGNORAR) is None, (
        "a ordem calada apareceu com o botão de dispensar de novo"
    )


# ---------------------------------------------------------------------------
# 2. A MORDIDA: zero ordens com uma checagem cega é CINZA, nunca verde.
# ---------------------------------------------------------------------------


def test_zero_ordens_com_checagem_cega_nao_e_verde() -> None:
    """`D-O-QUE-O-PRODUTO-DIZ-SEM-SABER` no topo da seção.

    Nenhuma ordem, quatro conferências respondendo e UMA que não soube. O topo
    tem de ficar cinza e DIZER que alguma coisa não deu resposta. Contar as
    cinco como conferidas produz "Nada a mudar. Conferi 5 coisas agora." — o
    estado em que o produto não sabe se disfarçando do estado em que está tudo
    bem, que é o F7 desta casa.
    """
    _janela, painel, _hospedeiro = montar()
    itens = [*CINCO_CERTAS[:-1], conferencia("vizinhanca_das_portas", "nao_sei")]

    aplicar(painel, itens)

    markup = painel.selo.get_label()
    esperado = ordens.cabecalho(
        ordens=[], conferidas=4, sem_resposta=1, dispensadas=0
    )
    assert esperado.chave == ordens.TOPO_ALGUMA_NAO_SOUBE
    assert secao.COR[exame_mod.ESTADO_CERTO] not in markup, (
        f"o topo saiu VERDE com uma checagem que não soube: {markup!r}"
    )
    assert secao.COR[exame_mod.ESTADO_NAO_SEI] in markup, (
        f"o topo não saiu cinza: {markup!r}"
    )
    assert esperado.texto in painel.selo.get_text(), (
        "o topo não disse que alguma coisa não deu resposta — ele contou a "
        "checagem cega como conferida, e a frase virou o estado bom.\n"
        f"  esperado: {esperado.texto!r}\n"
        f"  na tela:  {painel.selo.get_text()!r}"
    )


def test_o_verde_nunca_cobre_uma_linha_vermelha() -> None:
    """A cicatriz de `6c86e295`, e ela vale para o cabeçalho novo.

    `ordens_da_mesa.cabecalho()` não conhece `ESTADO_PROBLEMA`: sem ordens e
    sem checagem cega ele devolve o verde "Nada a mudar", mesmo com a linha de
    pareamentos em vermelho logo abaixo. Um topo pintado só por ele é a tela
    ensinando que verde-e-vermelho juntos são normais por aqui.
    """
    _janela, painel, _hospedeiro = montar()
    itens = [
        *CINCO_CERTAS[:-1],
        conferencia("pareamentos", exame_mod.ESTADO_PROBLEMA, cura="Pareie de novo"),
    ]

    aplicar(painel, itens)

    markup = painel.selo.get_label()
    assert secao.COR[exame_mod.ESTADO_PROBLEMA] in markup, (
        f"o topo não ficou vermelho sobre uma linha vermelha: {markup!r}"
    )
    assert secao.FRASE_DO_SELO[exame_mod.ESTADO_PROBLEMA] in painel.selo.get_text()


def test_o_estado_bom_diz_quanta_coisa_conferiu() -> None:
    """A queixa dela: *"o 'está tudo certo' não fala nada"*."""
    _janela, painel, _hospedeiro = montar()

    aplicar(painel, list(CINCO_CERTAS))

    esperado = ordens.cabecalho(
        ordens=[], conferidas=5, sem_resposta=0, dispensadas=0
    )
    assert esperado.texto in painel.selo.get_text()
    assert secao.COR[exame_mod.ESTADO_CERTO] in painel.selo.get_label()


def test_a_ordem_dispensada_nao_segura_o_topo_em_laranja() -> None:
    """Se o `[Ignorar]` não muda o topo, ele não fez nada visível.

    A ordem continua no exame — o produto não desaprendeu o que mediu. O que
    mudou é a decisão dela, e o topo tem de contá-la em vez de continuar
    alertando sobre o que ela mandou calar.
    """
    _janela, painel, _hospedeiro = montar()

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(uma_ordem())])
    assert secao.COR[exame_mod.ESTADO_ATENCAO] in painel.selo.get_label()

    botao(painel.cards, secao.ROTULO_IGNORAR).clicked()

    esperado = ordens.cabecalho(
        ordens=[], conferidas=5, sem_resposta=0, dispensadas=1
    )
    assert esperado.chave == ordens.TOPO_NADA_NOVO
    assert esperado.texto in painel.selo.get_text(), (
        f"o topo não contou a decisão dela: {painel.selo.get_text()!r}"
    )


# ---------------------------------------------------------------------------
# 3. "Já movi — reexaminar": as quatro respostas chegam à tela.
# ---------------------------------------------------------------------------


def apertar_ja_movi(
    painel: secao.PainelDoExame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aperta o botão sem deixar o exame de verdade sair para o barramento.

    `reexaminar()` submete um worker que lê `/sys`, o `maquina.json` e o rádio.
    O que este arquivo mede é o que a seção FAZ com o resultado, e o resultado
    entra pela mão do teste na chamada a `aplicar` seguinte.
    """
    chamou: list[int] = []
    monkeypatch.setattr(painel, "reexaminar", lambda: chamou.append(1))
    alvo = botao(painel.cards, secao.ROTULO_JA_MOVI)
    assert alvo is not None, (
        f"o card nasceu sem o botão {secao.ROTULO_JA_MOVI!r}"
    )
    alvo.clicked()
    assert chamou, "o botão não refez o exame"


def test_a_regra_parou_de_disparar_e_a_confirmacao_fica_na_tela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passagem 1: ela moveu e a regra calou.

    Um card que simplesmente some é indistinguível de um card que nunca foi
    desenhado. Ela apertou um botão e precisa ver o que ele fez — é o F7
    aplicado ao próprio gesto dela.
    """
    janela, painel, _hospedeiro = montar()

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(uma_ordem())])
    apertar_ja_movi(painel, monkeypatch)
    aplicar(painel, list(CINCO_CERTAS))

    juntos = " ".join(textos(janela))
    assert ordens.FRASE_DA_RESPOSTA[ordens.CONFIRMEI] in juntos, (
        "a regra parou de disparar e o card sumiu em silêncio: ela não tem "
        "como saber que o que fez resolveu"
    )
    assert secao.COR[exame_mod.ESTADO_CERTO] in " ".join(
        widget.get_label()
        for widget in arvore(painel.cards)
        if isinstance(widget, Gtk.Label) and widget.get_label()
    )


def test_o_arranjo_diferente_diz_que_ela_moveu_e_continua_apertado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passagem 2: ela moveu, e continua apertado — com o card NOVO."""
    janela, painel, _hospedeiro = montar()

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(uma_ordem())])
    apertar_ja_movi(painel, monkeypatch)
    nova = uma_ordem(arranjo=ARRANJO_DE_DEPOIS, acao="Mova para a entrada 4")
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(nova)])

    juntos = " ".join(textos(janela))
    assert ordens.FRASE_DA_RESPOSTA[ordens.MOVEU_E_CONTINUA] in juntos
    assert nova.acao in juntos, "a resposta apagou a ordem nova em vez de somar"


def test_o_mesmo_arranjo_diz_que_nao_viu_mudanca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passagem 3: nada mudou. O card FICA, com essa linha somada."""
    janela, painel, _hospedeiro = montar()
    ordem = uma_ordem()

    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])
    apertar_ja_movi(painel, monkeypatch)
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])

    juntos = " ".join(textos(janela))
    assert ordens.FRASE_DA_RESPOSTA[ordens.SEM_MUDANCA] in juntos
    assert ordem.acao in juntos


def test_a_tripla_ambigua_nunca_confirma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passagem 4: dois aparelhos iguais na mesa — **nunca** "Confirmei".

    A ambiguidade fina é a do SERIAL, e ela só existe porque a seção chama
    `identidades`: `_identidade_do_caminho` separa por `vid:pid`, e os três
    adaptadores desta casa são `2357:0604`. Sem a costura, o produto diria
    "Confirmei" sem saber qual dos dois ela moveu.
    """
    janela, painel, _hospedeiro = montar()
    ordem = uma_ordem()
    painel.aplicar(
        [*CINCO_CERTAS, item_da_ordem(ordem)],
        exame_mod.ESTADO_ATENCAO,
        time.time(),
        {ordem.alvo.caminho: ordens.Identidade(
            vid=ordem.alvo.vid,
            pid=ordem.alvo.pid,
            caminho=ordem.alvo.caminho,
            ambigua=True,
        )},
        {},
    )
    apertar_ja_movi(painel, monkeypatch)
    aplicar(painel, list(CINCO_CERTAS))

    juntos = " ".join(textos(janela))
    assert ordens.FRASE_DA_RESPOSTA[ordens.NAO_CONSEGUI_CONFIRMAR] in juntos
    assert ordens.FRASE_DA_RESPOSTA[ordens.CONFIRMEI] not in juntos, (
        "o produto confirmou com dois aparelhos indistinguíveis na mesa"
    )


def test_a_resposta_nao_sobrevive_ao_exame_seguinte() -> None:
    """"Fica até ela sair da aba" — e o refresher da aba é um exame novo.

    Sem esta limpeza, a frase de ontem ficaria colada num card de hoje, que é a
    zona de cards acumulando com outro nome.
    """
    janela, painel, _hospedeiro = montar()
    ordem = uma_ordem()
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])
    painel._aguardando[ordem.chave] = ordem
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])
    assert ordens.FRASE_DA_RESPOSTA[ordens.SEM_MUDANCA] in " ".join(textos(janela))

    painel.reexaminar()
    aplicar(painel, [*CINCO_CERTAS, item_da_ordem(ordem)])

    assert ordens.FRASE_DA_RESPOSTA[ordens.SEM_MUDANCA] not in " ".join(
        textos(janela)
    )


# ---------------------------------------------------------------------------
# 4. As réguas contra si mesmas.
# ---------------------------------------------------------------------------


def test_a_montagem_nao_desenha_botao_de_ordem_nenhum() -> None:
    """O estado que o retrato das abas fotografa: montado e ainda sem exame.

    A montagem não examina, então não há ordem — e um card com dois botões
    numa seção que nunca mediu nada seria a tela oferecendo um gesto sobre
    leitura nenhuma.
    """
    janela, painel, _hospedeiro = montar()

    assert painel.cards.get_children() == []
    assert botao(janela, secao.ROTULO_JA_MOVI) is None
    assert botao(janela, secao.ROTULO_IGNORAR) is None


def test_a_regua_dos_botoes_de_fato_acha_um_botao() -> None:
    """A régua contra si mesma: um localizador quebrado daria verde para sempre.

    Esta casa pagou por três instrumentos falsos num dia só. Aqui o custo seria
    silencioso: `botao(...)` devolvendo `None` faz as asserções de ausência
    passarem sobre uma tela cheia de botões.
    """
    janela, _painel, _hospedeiro = montar()

    assert botao(janela, secao.ROTULO_DO_BOTAO) is not None, (
        "a régua não achou o botão 'Examinar de novo', que está na tela desde "
        "25/08 — ela estava medindo nada"
    )
