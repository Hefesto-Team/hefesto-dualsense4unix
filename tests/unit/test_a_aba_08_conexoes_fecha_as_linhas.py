#!/usr/bin/env python3
"""As decisões do PO sobre a aba `08-conexoes`, medidas na SAÍDA do produto.

**A RÉGUA LÊ, NÃO DIGITA.** Cada teste aqui pergunta ao produto (a função do
pacote, a página gravada) e compara com o que os DONOS dizem — nunca com uma
segunda cópia da frase escrita no teste. Esta casa pagou onze vezes em 26/08 por
réguas que digitavam o que deviam ler, e elas reprovavam a melhora em vez do
defeito.

As decisões cobertas, todas de `docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`,
§2, aba `08-conexoes`:

* **[03]** cartão de cura na coluna da direita;
* **[04]** selo de procedência só nas frases que não foram medidas aqui;
* **[07]** o `+N` no fim de cada lista;
* **[08]** a frase do rodapé do Mapa, trocada pela verdade.

E o defeito da §3 desta aba: **o campo de nome do adaptador promete e não
guarda.**
"""

from __future__ import annotations

import re

import pytest


@pytest.fixture()
def pacote():
    """O pacote da aba, importado uma vez por teste."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture()
def cena():
    """Uma cena de exame com as DUAS formas que a coluna da direita desenha.

    Ela imita o que esta bancada mediu em 03/09/2026 — duas ordens abertas e
    conferências com cura — sem tocar no barramento: os objetos são os do
    produto (`exame_da_mesa.Item`, `ordens_da_mesa.Ordem`), montados à mão.
    """
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        MEDIDO_AQUI,
        Linha,
        Ordem,
    )

    def ordem(chave: str) -> Ordem:
        return Ordem(
            chave=chave,
            acao=f"Mova o adaptador de {chave}",
            o_que_eu_vi=Linha(texto="dois rádios na mesma raiz", selo=MEDIDO_AQUI),
            por_que_importa=Linha(texto="USB 3.0 faz ruído em 2,4 GHz",
                                  selo=DERIVADO_DA_CONTA),
            ganho_esperado=Linha(texto="menos engasgo no rádio",
                                 selo=DERIVADO_DA_CONTA),
            arranjo="3-1|3-2",
        )

    # OS ESTADOS SÃO LIDOS DO DONO, e não digitados: `exame_da_mesa` exporta as
    # chaves de máquina (ASCII por contrato), e uma cena que as digitasse
    # continuaria verde no dia em que uma delas mudasse de grafia.
    from hefesto_dualsense4unix.integrations.exame_da_mesa import (
        ESTADO_ATENCAO,
        ESTADO_CERTO,
        ESTADO_NAO_SEI,
    )

    return [
        Item(chave="uma", rotulo="A", estado=ESTADO_ATENCAO, porque="vi isto",
             cura="mova o cabo", ordem=ordem("uma")),
        Item(chave="outra", rotulo="B", estado=ESTADO_ATENCAO, porque="vi aquilo",
             cura="tire o hub", ordem=ordem("outra")),
        Item(chave="conf-1", rotulo="C", estado=ESTADO_ATENCAO,
             porque="a economia de energia está ligada",
             cura="desligue a economia de energia"),
        Item(chave="conf-2", rotulo="D", estado=ESTADO_CERTO,
             porque="as entradas dão 500 mA", cura="não precisa fazer nada"),
        Item(chave="conf-3", rotulo="E", estado=ESTADO_NAO_SEI,
             porque="não consegui olhar", cura=None),
    ]


# ---------------------------------------------------------------------------
# [04] O SELO DE PROCEDÊNCIA — só nas frases que NÃO foram medidas aqui
# ---------------------------------------------------------------------------
def test_a_marca_de_procedencia_cala_no_medido_aqui(pacote) -> None:
    """`medido aqui` é o implícito, e o implícito não ocupa pixel.

    MORDE: um `_marca_da_procedencia` que devolvesse a marca sempre poria três
    marcas de cinza num balão de 330 px — que é a medição pela qual esta marca
    tinha ficado FORA até hoje.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        MEDIDO_AQUI,
        Linha,
    )

    assert pacote._marca_da_procedencia(Linha(texto="x", selo=MEDIDO_AQUI)) == ""


def test_a_marca_de_procedencia_diz_a_palavra_do_dono(pacote) -> None:
    """A palavra sai de `ordens_da_mesa.TEXTO_DO_SELO` — nunca digitada aqui."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        TEXTO_DO_SELO,
        Linha,
    )

    saiu = pacote._marca_da_procedencia(Linha(texto="x", selo=DERIVADO_DA_CONTA))
    assert TEXTO_DO_SELO[DERIVADO_DA_CONTA] in saiu
    assert saiu.startswith(" <span")


def test_a_dica_da_ordem_marca_so_a_frase_derivada(pacote, cena) -> None:
    """As DUAS frases do `?`, e a marca só na segunda.

    A CENA É LIDA, não afirmada: o teste pergunta ao objeto qual selo cada linha
    tem e conta as marcas — uma régua que contasse "1" sem olhar os selos
    passaria com a cena trocada.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        MEDIDO_AQUI,
        TEXTO_DO_SELO,
    )

    ordem = cena[0].ordem
    dica = pacote._dica_da_ordem(ordem)
    esperadas = sum(1 for linha in ordem.linhas[:2] if linha.selo != MEDIDO_AQUI)
    assert dica.count('class="proc"') == esperadas
    assert TEXTO_DO_SELO[MEDIDO_AQUI] not in dica


# ---------------------------------------------------------------------------
# [03] O CARTÃO DE CURA + [07] O `+N`
# ---------------------------------------------------------------------------
def _coluna(pacote, cena) -> str:
    """A coluna da direita como o produto a emite, com a cena na mão."""
    pacote._ORDENS_NA_TELA = tuple(i.ordem for i in cena)
    return pacote._html_da_ordem(cena)


def test_a_coluna_desenha_um_cartao_por_cura_de_conferencia(pacote, cena) -> None:
    """Decisão [03] — e a regra dos três filtros é a do dono.

    O NÚMERO SAI DA CENA, e não de um literal: o teste refaz o filtro de
    `secao_exame._desenhar_o_que_fazer` (sem ordem · com cura · estado diferente
    de CERTO) e exige esse tanto de cards. Com a cena trocada, o número muda
    junto — que é o que separa uma régua de um carimbo.
    """
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO

    quantas = sum(1 for i in cena
                  if i.ordem is None and i.cura and i.estado != ESTADO_CERTO)
    assert quantas, "a cena precisa ter ao menos uma cura, senão o teste não mede nada"
    assert _coluna(pacote, cena).count('class="ordem cura"') == quantas


def test_o_cartao_de_cura_traz_a_cura_e_nao_traz_selo(pacote, cena) -> None:
    """A cura na tela, e SEM procedência — regra do dono, não economia.

    `secao_exame._card_da_cura`: *"uma cura de conferência não traz selo de
    procedência, porque não há medição por trás dela dizendo de onde vem o
    conselho."*
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA

    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO

    item = next(i for i in cena
                if i.ordem is None and i.cura and i.estado != ESTADO_CERTO)
    card = pacote._card_da_cura(item)
    assert PREFIXO_DA_CURA in card
    assert item.cura in card
    assert item.porque in card
    assert 'class="proc"' not in card


def test_o_mais_n_conta_a_ordem_que_nao_coube(pacote, cena) -> None:
    """Decisão [07] — a segunda ordem de 03/09 deixa de sumir.

    O DESENHO TEM UM CARD e esta cena tem DUAS ordens abertas; a diferença é o
    que a linha diz. O número sai da cena.
    """
    abertas = sum(1 for i in cena if i.ordem is not None)
    coluna = _coluna(pacote, cena)
    assert f"+{abertas - 1} " in coluna
    assert 'class="mais"' in coluna


def test_o_mais_n_cala_quando_tudo_cabe(pacote) -> None:
    """*"Só custa linha no dia em que sobra."* — e hoje ele não sobra."""
    assert pacote._sobraram(1, 1, "cura", "curas") == ""
    assert pacote._sobraram(0, 4, "cura", "curas") == ""


def test_o_mais_n_concorda_em_numero(pacote) -> None:
    """Uma coisa que não coube fala no singular; duas, no plural.

    Português com acentuação é regra desta casa, e uma tela que diz "+1 curas"
    é a mesma falta de cuidado que um número errado.
    """
    assert "1 cura não coube" in pacote._sobraram(5, 4, "cura", "curas")
    assert "2 curas não couberam" in pacote._sobraram(6, 4, "cura", "curas")


def test_a_coluna_sem_a_lista_continua_sendo_so_o_card(pacote) -> None:
    """O padrão não mudou: `_html_da_ordem()` sem cena é o que ela era.

    Isto é a garantia de que a decisão nova não vaza para quem ainda chama a
    função com a assinatura velha — e há um chamador assim: a régua de gestos.
    """
    pacote._ORDENS_NA_TELA = ()
    assert "cura" not in pacote._html_da_ordem()


# ---------------------------------------------------------------------------
# [08] A FRASE DO RODAPÉ DO MAPA
# ---------------------------------------------------------------------------
def test_o_rodape_do_mapa_nao_manda_apertar_o_aplicar() -> None:
    """Decisão [08] — *"Trocar pela verdade."*

    A frase velha mandava apertar um "Aplicar" que faz OUTRA coisa: a dica dele
    diz *"Vale agora: envia a configuração aos controles na hora. NÃO grava"*.
    Os seis gestos do mapa gravam no clique desde 01/09.

    A RÉGUA LÊ A BANCADA, que é onde o desenho de hoje mora.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert "mm-aplicar" in html, (
        "a linha do rodapé do Mapa sumiu — o teste não mede mais nada")
    assert "clicar em Aplicar" not in html


def test_o_rodape_do_mapa_diz_que_o_clique_ja_gravou() -> None:
    """E a frase nova é a do DONO desta aba, lida no ato.

    **O ENDEREÇO MUDOU EM 06/09/2026, `ONDA5-08-02`, e o TEXTO não.** Até aqui a
    régua lia `aba08.MAPA_JA_GRAVOU` — um literal DIGITADO no gerador, que é a
    dívida que aquela sprint pagou. Agora lê o dono, `mapa_da_mesa`, e a frase
    na página continua byte a byte a mesma.
    """
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import GRAVA_NO_CLIQUE
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert GRAVA_NO_CLIQUE in html


def test_o_rodape_do_mapa_vem_do_dono() -> None:
    """A frase do rodapé tem UM dono, e o gerador não guarda uma segunda cópia.

    **A DÍVIDA QUE ISTO FECHA:** entre 04/09 e 06/09 a linha era um literal em
    `interface/aba08.py`, enquanto os quatro rótulos vizinhos da mesma
    janelinha já saíam do produto por AST. Uma frase digitada no gerador vira a
    segunda versão dela no dia em que o produto a corrigir — e **régua nenhuma
    desta casa compara HTML com Python**, então o desvio seria silencioso. Esta
    é a régua que faltava.

    Ela cobra as DUAS pontas, porque uma sozinha passa por acidente:

    1. **o dono chega às duas páginas** — a bancada e a publicada; e a
       comparação é de IGUALDADE com o texto do nó `.mm-aplicar`, não um `in`
       frouxo sobre o arquivo inteiro;
    2. **o gerador não digita a frase** — nem no corpo nem em comentário. O
       `MAPA` continua sendo a única porta, e o `_constantes` que o monta
       derruba a geração quando o nome some do produto.
    """
    import pathlib

    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import GRAVA_NO_CLIQUE
    from hefesto_dualsense4unix.interface import aba08, onde

    for publicado in (False, True):
        pagina = onde.pagina("08-conexoes.html", publicado=publicado)
        html = pagina.read_text(encoding="utf-8")
        no = re.findall(r'<div class="tn-frase mm-aplicar">(.*?)</div>', html)
        assert len(no) == 1, (
            f"{pagina.name} ({'publicada' if publicado else 'bancada'}) tem "
            f"{len(no)} rodapé(s) `.mm-aplicar` — seletor que casa zero é ERRO, "
            f"não silêncio")
        assert no[0] == GRAVA_NO_CLIQUE, (
            f"o rodapé da página {'publicada' if publicado else 'da bancada'} "
            f"não é o do dono:\n  página: {no[0]!r}\n  dono:   {GRAVA_NO_CLIQUE!r}")

    fonte = pathlib.Path(aba08.__file__).read_text(encoding="utf-8")
    assert GRAVA_NO_CLIQUE not in fonte, (
        "`aba08.py` voltou a DIGITAR a frase do rodapé — ela tem dono, e o "
        "gerador a lê por `MAPA[\"GRAVA_NO_CLIQUE\"]`")
    assert aba08.MAPA["GRAVA_NO_CLIQUE"] == GRAVA_NO_CLIQUE, (
        "o `MAPA` do gerador deixou de carregar a frase — sem ela no conjunto "
        "do `_constantes`, renomear no produto some da tela em silêncio")


# ---------------------------------------------------------------------------
# O `?` DA QUINTA LINHA — um fato errado, e fato errado se SUBSTITUI
# ---------------------------------------------------------------------------
def test_o_exame_nao_manda_procurar_um_botao_que_nao_existe() -> None:
    """*"Ver as ordens ignoradas"* saiu da tela em 31/08 e a frase ficou.

    O `?` da quinta linha do Check-up e a dica do ⊘ mandavam procurar um botão
    que não existe mais. Isto não é decisão medida a preservar: é uma frase que
    a medição derrubou, e ela sai de TODO lugar em que fala do PRESENTE.

    **A RÉGUA MEDE O QUE A TELA DIZ, e não o arquivo inteiro:** o nome do botão
    sobrevive na retrospectiva do fim da página e nos comentários do gerador, e
    ali ele é verdadeiro — conta por que a fileira de quatro botões existiu. O
    que se cobra é que nenhuma DICA e nenhum `?` do miolo o cite.
    """
    from hefesto_dualsense4unix.interface import aba08, onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    dicas = re.findall(r'title="([^"]*)"', html)
    dicas += re.findall(r'data-campo="achado-explica"[^>]*>(.*?)</span>', html)
    assert dicas, "a régua não achou dica nenhuma — seletor cego é ERRO, não silêncio"
    citam = [d for d in dicas if aba08.VER_IGNORADAS in d]
    assert not citam, f"{len(citam)} dica(s) ainda mandam procurar um botão que não existe"
    assert aba08.VER_IGNORADAS in html, (
        "a retrospectiva perdeu o nome do botão — a régua deixa de separar as "
        "duas metades e passaria por acidente")


def test_a_frase_nova_diz_o_que_o_produto_faz() -> None:
    """E o que entrou no lugar é o que `ordens_da_mesa.ordens_novas` faz.

    A dispensa é gravada com o ARRANJO, e a linha volta sozinha quando o arranjo
    muda. As DUAS dicas passam a dizer isso — a do ⊘ e a da quinta linha.
    """
    from hefesto_dualsense4unix.interface import aba08, onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert html.count(aba08.ORDEM_IGNORADA_VOLTA) >= 2
    assert "A linha fica apagada aqui" not in html


# ---------------------------------------------------------------------------
# O DEFEITO DA §3 — o nome do adaptador promete e não guarda
# ---------------------------------------------------------------------------
def test_o_campo_do_nome_do_adaptador_tem_gesto(pacote) -> None:
    """Ela digita e o produto tem onde ouvir — o defeito da §3 desta aba.

    ATÉ HOJE a célula era `contenteditable` e mais nada: nenhum gesto,
    nenhum chamador de `apelido_do_dongle` na interface nova. *Ela vai digitar e
    perder.*

    A RÉGUA LÊ A TABELA QUE O PRODUTO EMITE, não o gerador — e aceita a mesa
    vazia, porque uma bancada sem adaptador não é defeito desta aba.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    assert ("08-conexoes.html", pacote.GESTO_DO_APELIDO) in GESTOS
    tabela = pacote._html_dos_adaptadores()
    linhas = re.findall(r'<span class="renomeia"[^>]*>', tabela)
    for linha in linhas:
        assert f'data-hef-gesto="{pacote.GESTO_DO_APELIDO}"' in linha
        assert "data-caminho=" in linha


def test_renomear_recusa_dizendo_sem_o_alvo(pacote) -> None:
    """*"Recusar dizendo é obrigatório."* — e o dublê tem de saber recusar."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    gesto = GESTOS[("08-conexoes.html", pacote.GESTO_DO_APELIDO)]
    with pytest.raises(ValueError):
        gesto(None, {"texto": "Sala"}, None)


def test_renomear_nao_escreve_quando_o_nome_nao_mudou(pacote, monkeypatch) -> None:
    """O mesmo nome não vai ao barramento — a regra é a da janela estável.

    `secao_mesa._ao_salvar_o_nome`: *"Sem ela, cada troca de aba reescreveria o
    alias dos três adaptadores com o valor que eles já têm — escrita à toa num
    barramento de sistema, e uma delas cairia bem em cima do prefixo que segura
    o Pro."*

    MORDE: sem a comparação, este teste vê o escritor ser chamado.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    from hefesto_dualsense4unix.integrations.apelido_do_dongle import Renomeacao

    chamou: list[str] = []

    def _escreveu(endereco: str, nome: str) -> Renomeacao:
        chamou.append(nome)
        return Renomeacao(endereco=endereco, nome=nome, aplicado=True)

    monkeypatch.setattr(pacote, "_endereco_e_nome_do_adaptador",
                        lambda caminho: ("AA:BB:CC:00:00:01", "Sala"))
    monkeypatch.setattr(pacote, "_gravar_o_apelido", _escreveu)
    gesto = GESTOS[("08-conexoes.html", pacote.GESTO_DO_APELIDO)]
    gesto(None, {"caminho": "3-1.2", "texto": "Sala"}, None)
    assert chamou == []
    gesto(None, {"caminho": "3-1.2", "texto": "Sala do fundo"}, None)
    assert chamou == ["Sala do fundo"]


def test_o_escritor_do_apelido_chama_o_dono_com_a_assinatura_dele(
    pacote, monkeypatch
) -> None:
    """A ASSINATURA, e não só o nome — a cicatriz de 04/09/2026.

    *"Duas vezes em 04/09 um gesto passou VERDE sem gravar um byte: uma porque o
    dicionário ia como `timeout` posicional, outra porque `_run_blocking` não
    aceita keywords."* Aqui a régua fixa o contrato: `renomear_o_dongle` recebe
    o BD Address e o nome POSICIONAIS, e a leitura de mão em `dongles=` — que é
    a economia de varredura que o dono documenta.
    """
    from hefesto_dualsense4unix.integrations import apelido_do_dongle

    visto: dict[str, object] = {}

    def _falso(endereco, nome, **kw):
        visto.update(endereco=endereco, nome=nome, **kw)
        return apelido_do_dongle.Renomeacao(
            endereco=endereco, nome=nome, aplicado=True)

    monkeypatch.setattr(apelido_do_dongle, "renomear_o_dongle", _falso)
    monkeypatch.setattr(pacote, "_dongles", lambda recarregar=False: ())
    feito = pacote._gravar_o_apelido("AA:BB:CC:00:00:01", "Sala do fundo")
    assert feito.aplicado
    assert visto["endereco"] == "AA:BB:CC:00:00:01"
    assert visto["nome"] == "Sala do fundo"
    assert "dongles" in visto, (
        "a leitura de mão não foi passada — o dono varreria o barramento de novo")


# ---------------------------------------------------------------------------
# 08-Q5 — A ORDEM CALADA FICA NA TELA, E O MESMO ⊘ DESFAZ
#
# Palavra dela, 05/09/2026: *"A recomendação calada continua no lugar dela, em
# cinza, e o mesmo botão desfaz."* A trava que ela leu era a medição desta casa:
# *"Hoje não há caminho de volta nenhum."*
#
# O `_DISPENSADAS` É GLOBAL DE MÓDULO, e por isso todo teste daqui para baixo
# passa pelo `mesa` abaixo: salvar e devolver os três globais é o que impede que
# uma cena vaze para o teste seguinte — o defeito de ordem de teste que esta
# casa mediu três vezes em 05/09.
# ---------------------------------------------------------------------------
@pytest.fixture()
def mesa(pacote):
    """Põe uma cena na tira e devolve a máquina ao que era. Sempre.

    Devolve uma função `(itens, dispensadas) -> None`; o `finally` repõe
    `_conferencias`, `_EXTRAS` e `_DISPENSADAS` mesmo quando o teste falha.
    """
    antes = (pacote._conferencias, pacote._EXTRAS, dict(pacote._DISPENSADAS),
             pacote._ORDENS_NA_TELA)

    def por(itens, dispensadas=None):
        pacote._conferencias = lambda: []
        pacote._EXTRAS = tuple(itens)
        pacote._DISPENSADAS = dict(dispensadas or {})
        pacote._ORDENS_NA_TELA = tuple(getattr(i, "ordem", None) for i in itens)

    yield por
    (pacote._conferencias, pacote._EXTRAS,
     pacote._DISPENSADAS, pacote._ORDENS_NA_TELA) = antes


def _dispensa_a_primeira(cena) -> dict[str, str]:
    """`{chave: arranjo}` da primeira ordem da cena — LIDO dela, não digitado."""
    ordem = next(i.ordem for i in cena if i.ordem is not None)
    return {ordem.chave: ordem.arranjo}


def test_a_ordem_calada_continua_na_tira(pacote, cena, mesa) -> None:
    """08-Q5 — a linha que ela calou **não sai da lista**.

    MORDE: devolva o `continue` que `_itens_da_tela` tinha até 05/09 e a tira
    volta a ter um item a menos — a porta de mão única sobre um clique dela.

    O NÚMERO SAI DA CENA, e não de um literal: com a cena trocada ele muda
    junto.
    """
    mesa(cena, _dispensa_a_primeira(cena))
    tira = pacote._itens_da_tela()
    assert len(tira) == len(cena), (
        f"a tira perdeu itens: {[i.chave for i in tira]} — a ordem calada "
        "sumiu, que é a porta de mão única que a 08-Q5 fecha")
    caladas = [i.chave for i in tira if pacote._calada(i)]
    assert caladas == [next(i.chave for i in cena if i.ordem is not None)], (
        f"a marca da linha calada não caiu na linha certa: {caladas}")


def test_a_ordem_calada_com_arranjo_vazio_nao_cala(pacote, cena, mesa) -> None:
    """A borda do arranjo vazio, e ela é o preço do desfazer.

    O desfazer grava `arranjo=""` na mesma chave, e `Ordem.arranjo` tem `""` por
    PADRÃO. Sem o `and arranjo` da guarda, uma ordem viva sem assinatura casaria
    com o vazio guardado e nasceria calada — a tela apagando um achado que
    ninguém dispensou.

    MORDE: tire o `bool(arranjo) and` de `_ordem_calada` e este teste vê a linha
    nascer cinza.
    """
    import dataclasses

    item = next(i for i in cena if i.ordem is not None)
    sem_assinatura = dataclasses.replace(item.ordem, arranjo="")
    mesa([dataclasses.replace(item, ordem=sem_assinatura)],
         {sem_assinatura.chave: ""})
    tira = pacote._itens_da_tela()
    assert len(tira) == 1
    assert not pacote._calada(tira[0]), (
        "uma ordem VIVA sem assinatura de arranjo nasceu calada — o vazio "
        "guardado pelo desfazer casou com o vazio do padrão")


def test_a_aba_jogar_nao_recebe_a_ordem_calada(pacote, cena, mesa) -> None:
    """Passo 2 — `_exame()` é CONTRATO, e o consumidor é outra aba.

    `a01_jogar._do_exame` leva tudo o que for `grave` para a coluna **Atenção**.
    Sem este filtro, calar um alarme na Conexões o deixaria aceso na Jogar — a
    mesma contradição de duas telas que o `_do_exame` de lá existe para não ter.

    A RÉGUA CHAMA A ABA 01, e não o `_exame` daqui: o que se prova é o contrato
    inteiro, não a função de um lado dele.

    MORDE: tire o filtro de `_exame()` e a chave calada reaparece na lista que a
    Jogar consome.
    """
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    dispensada = _dispensa_a_primeira(cena)
    mesa(cena, dispensada)
    calada = next(iter(dispensada))
    assert calada in [i.chave for i in pacote._itens_da_tela()], (
        "a cena não tem a linha calada na tira — o teste não mede nada")
    assert calada not in [i["chave"] for i in a01_jogar._do_exame()], (
        "a aba Jogar recebeu a ordem que ela calou na Conexões")


def test_a_linha_que_voltou_apaga_a_tinta(pacote, cena, mesa) -> None:
    """Passo 3 — a chave `calada` vai em TODO tique, inclusive vazia.

    É a mesma regra do botão cinza da ONDA0-F: a chave que só aparece quando há
    o que dizer deixa na tela a tinta do tique anterior — e a linha que VOLTOU
    ficaria cinza para sempre.

    MORDE: emita `calada` só quando for `"sim"` e a segunda leitura perde a
    chave, que é a linha continuando cinza depois do desfazer.
    """
    dispensada = _dispensa_a_primeira(cena)
    mesa(cena, dispensada)
    antes = [pacote._linha(i)["calada"] for i in pacote._itens_da_tela()]
    assert antes.count("sim") == 1, f"a cena não calou uma linha só: {antes}"

    # O DESFAZER, como o gesto o escreve: `arranjo=""` na mesma chave.
    pacote._DISPENSADAS[next(iter(dispensada))] = ""
    depois = [pacote._linha(i)["calada"] for i in pacote._itens_da_tela()]
    assert len(depois) == len(antes), "a tira mudou de tamanho no desfazer"
    assert depois.count("sim") == 0, (
        f"a linha continuou marcada como calada depois do desfazer: {depois}")
    assert all(v == "" for v in depois), (
        "a chave sumiu em vez de vir VAZIA — o piloto não visitaria o elemento "
        f"e a tinta do tique anterior ficaria: {depois}")


def test_o_desenho_tem_endereco_para_a_linha_apagada() -> None:
    """Passo 4 — a régua LÊ a página, e cobra as três metades do alvo `classe`.

    O alvo `classe` do piloto precisa de `data-campo` (o endereço),
    `data-hef-alvo="classe"` (o alvo), `data-hef-classe` (que classe acender) e
    `data-hef-quando` (com que valor). Faltando uma, o endereço existe e não
    pinta — o silêncio que esta casa chama de endereço morto.

    E A FOLHA TEM DE SABER DESENHAR A CLASSE, senão a linha calada fica
    idêntica à que fala: endereço vivo pintando uma classe que ninguém estilizou
    é a mesma tela de antes, com mais atributos.

    MORDE: tire o `data-hef-classe="apagada"` do `<div>` e a primeira asserção
    reprova; tire a regra `.exame.apagada` da folha e a última reprova.
    """
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    linhas = re.findall(r'<div class="exame"[^>]*>', html)
    assert len(linhas) == p.TETO_DO_EXAME, (
        f"o desenho tem {len(linhas)} linhas de exame e o teto do produto é "
        f"{p.TETO_DO_EXAME} — seletor cego é ERRO, não silêncio")
    for div in linhas:
        assert 'data-campo="exame-calada"' in div, div
        assert 'data-hef-alvo="classe"' in div, div
        assert 'data-hef-classe="apagada"' in div, div
        assert 'data-hef-quando="sim"' in div, div
    assert re.search(r"\.exame\.apagada[^{]*\{[^}]*opacity", html), (
        "a folha não ESMAECE a linha calada — o endereço pintaria uma classe "
        "sem estilo, e a linha cinza ficaria igual à que fala. A régua cobra a "
        "regra que dim, e não a presença do nome: uma folha que só troca a cor "
        "do glifo passaria por ela sem apagar nada")
    assert not re.search(r"\.exame\.apagada[^{]*\{[^}]*display:none", html), (
        "a linha calada SOME em vez de esmaecer — a decisão dela diz que ela "
        "*continua no lugar dela*, e uma linha que some é a tela que esconde")


def test_a_dica_do_ignorar_vem_do_produto() -> None:
    """Passo 4 — o ⊘ muda de sentido, e a dica tem de mudar com ele.

    Até 05/09 o `title` era CRAVADO no gerador e mentia duas vezes: dizia *"A
    recomendação sai desta lista"* (a linha passou a ficar) e continuava dizendo
    a mesma coisa depois do clique. **Um botão que muda de sentido com uma dica
    congelada é a cicatriz da trava da luz, medida em 04/09.**

    A RÉGUA LÊ A PÁGINA e compara com o DONO da frase (`a08_conexoes`), nunca
    com uma segunda cópia escrita aqui.

    MORDE: tire o `data-campo="ignorar-dica"` do `<button>` e a dica volta a ser
    a congelada do desenho.
    """
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    botoes = re.findall(r'<button class="ignora"[^>]*>', html)
    assert len(botoes) == p.TETO_DO_EXAME, (
        f"a régua achou {len(botoes)} glifos de ignorar — seletor cego é ERRO")
    for b in botoes:
        assert 'data-campo="ignorar-dica"' in b, b
        assert 'data-hef-alvo="atributo"' in b, b
        assert 'data-hef-atributo="title"' in b, b
        assert f'title="{p.DICA_DO_IGNORAR}"' in b, (
            f"o `title` de partida não é o do dono: {b}")
    assert "sai desta lista" not in html, (
        "a frase que a 08-Q5 tornou falsa sobreviveu em algum lugar da tela — "
        "fato errado se SUBSTITUI, e sai de TODOS os lugares")


def test_o_mesmo_gesto_desfaz(pacote, cena, mesa) -> None:
    """Passo 5 — o ⊘ é um INTERRUPTOR, e o segundo clique traz de volta.

    *"o mesmo botão desfaz"* (08-Q5). O desfazer grava `arranjo=""` na mesma
    chave, porque `machine.declare` não tem verbo de remoção — e um arranjo
    vazio guardado não casa com arranjo nenhum, logo a ordem volta a falar.

    O DUBLÊ GUARDA O QUE FOI GRAVADO, e a régua lê o disco de mentira: contar
    chamadas provaria que a função rodou, não que ela escreveu a coisa certa.

    MORDE: faça o gesto gravar sempre a dispensa (o de 05/09) e o segundo
    clique deixa a linha calada em vez de trazê-la de volta.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})
    gravado: list[dict] = []

    class _Ponte:
        """O que `ipc_bridge.machine_declare` devolve: `(ok, motivo)`.

        NÃO um `{"ok": True}`: `_resposta` faz `bool(r)` num objeto que não é
        tupla, e **todo dicionário não vazio é verdadeiro** — um dublê assim
        aprova a recusa junto com o sucesso. É o dublê mais frouxo que o real,
        que derrubou três réguas em 05/09.
        """

        def machine_declare(self, carga):
            gravado.append(carga["mesa"]["ordens_dispensadas"])
            return (True, "")

    gesto = GESTOS[("08-conexoes.html", "ignorar")]
    posicao = next(i for i, item in enumerate(cena) if item.ordem is not None)
    ordem = cena[posicao].ordem

    # `_reler_a_declaracao` VAI AO DISCO. O que este teste mede é o gesto, e
    # deixá-lo ler o `maquina.json` do lar de mentira faria a régua depender de
    # um arquivo que ela não escreveu.
    antes_reler = pacote._reler_a_declaracao
    pacote._reler_a_declaracao = lambda: None
    try:
        gesto(None, {"v": str(posicao)}, _Ponte())
        assert pacote._calada(cena[posicao]), "o primeiro clique não calou"
        assert gravado[-1][ordem.chave]["arranjo"] == ordem.arranjo
        assert gravado[-1][ordem.chave]["quando"], (
            "a dispensa foi gravada sem data — `quando` é o que diz quando ela "
            "decidiu")

        gesto(None, {"v": str(posicao)}, _Ponte())
        assert not pacote._calada(cena[posicao]), (
            "o segundo clique não desfez — o ⊘ continua sendo porta de mão única")
        assert gravado[-1][ordem.chave] == {"quando": "", "arranjo": ""}, (
            f"o desfazer não escreveu os dois vazios: {gravado[-1]}")
    finally:
        pacote._reler_a_declaracao = antes_reler


def test_o_desfazer_passa_no_esquema_do_disco() -> None:
    """E os dois vazios têm de sobreviver ao pydantic, senão o desfazer é teoria.

    `OrdemDispensada._so_a_data` só cobra a forma do que NÃO é vazio, e
    `_assinatura_sem_identidade` só cobra teto e cara de endereço. A régua
    pergunta ao DONO do esquema em vez de afirmar que ele aceita.
    """
    from hefesto_dualsense4unix.utils.maquina import MesaDeclarada

    mesa = MesaDeclarada.model_validate(
        {"ordens_dispensadas": {"dongle_atras_de_hub": {"quando": "", "arranjo": ""}}})
    assert mesa.ordens_dispensadas["dongle_atras_de_hub"].arranjo == ""


def test_a_recusa_do_disco_nao_cala_a_linha(pacote, cena, mesa) -> None:
    """Passo 5 — a ordem disco→memória não se inverte.

    `_declarar` LEVANTA quando o daemon recusa. Se a memória mudasse primeiro, a
    tela ficaria num estado que o disco não tem — e a linha voltaria sozinha no
    tique seguinte, sem uma palavra. É perder decisão dela em silêncio.

    **O DUBLÊ TEM DE SABER RECUSAR**, e é por isso que este teste existe
    separado: um dublê que só sabe dizer `{"ok": True}` nunca exercita o caminho
    de erro, e três vermelhos de 05/09 foram exatamente isso.

    MORDE: ponha o `_DISPENSADAS[...] = …` antes do `_declarar` e a linha
    aparece calada mesmo com o disco tendo recusado.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})

    class _PonteQueRecusa:
        def machine_declare(self, carga):
            return (False, "não consegui gravar agora")

    gesto = GESTOS[("08-conexoes.html", "ignorar")]
    posicao = next(i for i, item in enumerate(cena) if item.ordem is not None)
    with pytest.raises(RuntimeError):
        gesto(None, {"v": str(posicao)}, _PonteQueRecusa())
    assert not pacote._calada(cena[posicao]), (
        "a linha calou com o disco tendo RECUSADO — a tela num estado que o "
        "disco não tem, e a linha volta sozinha no tique seguinte")


def test_o_ignorar_numa_conferencia_continua_recusando_dizendo(pacote, cena, mesa) -> None:
    """Nada se perdeu: uma conferência não tem arranjo, e o ⊘ nela recusa.

    Gravar ali criaria uma chave que regra nenhuma consulta.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})
    posicao = next(i for i, item in enumerate(cena) if item.ordem is None)
    with pytest.raises(RuntimeError):
        GESTOS[("08-conexoes.html", "ignorar")](None, {"v": str(posicao)}, None)


def test_o_mais_n_do_exame_cala_sem_travessao(pacote) -> None:
    """Passo 6 — quando cabe tudo, a linha não pode virar um `—` na tela dela.

    O `escrever()` do piloto troca valor vazio por travessão ANTES de olhar o
    alvo. Um `""` daqui poria um `—` solto sob a quinta linha do exame todo dia,
    que é ruído com cara de dado — e é para isso que o `monta.NADA_A_DIZER`
    existe, com a folha escondendo a linha por `:has(.nada)`.

    MORDE: mande `""` em vez do `NADA_A_DIZER` e as duas asserções reprovam.
    """
    nada = pacote._monta().NADA_A_DIZER
    fora = pacote._o_que_nao_coube([1] * pacote.TETO_DO_EXAME,
                                   [1] * pacote.TETO_DE_VIZINHOS)
    assert fora["exame-mais"] == nada, fora
    assert fora["vizinho-mais"] == nada, fora
    assert all(v for v in fora.values()), (
        "uma das chaves veio VAZIA — o piloto a traduziria em `—`")


def test_cada_mais_n_conta_a_propria_lista(pacote) -> None:
    """Passo 6 — a conta da lista errada, que esta aba já cometeu uma vez.

    `gui.aba_conexoes.sobraram` está citado em quatro lugares desta árvore como
    dono desta frase, e ele conta o ACORDEÃO. Aqui cada `+N` conta a lista que
    ele legenda.

    MORDE: faça o `+N` do exame contar a lista dos vizinhos e as duas asserções
    trocam de número.
    """
    quantos_no_exame = pacote.TETO_DO_EXAME + 2
    quantos_vizinhos = pacote.TETO_DE_VIZINHOS + 1
    fora = pacote._o_que_nao_coube([1] * quantos_no_exame, [1] * quantos_vizinhos)
    assert f"+{quantos_no_exame - pacote.TETO_DO_EXAME} " in fora["exame-mais"], fora
    assert "achado" in fora["exame-mais"], fora
    assert f"+{quantos_vizinhos - pacote.TETO_DE_VIZINHOS} " in fora["vizinho-mais"], fora
    assert "rádio vizinho" in fora["vizinho-mais"], fora


def test_o_desenho_tem_onde_dizer_o_que_nao_coube() -> None:
    """E os dois endereços têm de existir na página — senão a conta não chega.

    A peça é a `monta.ressalva`, que a folha esconde por `:empty` e `:has(.nada)`
    — a linha só existe no dia em que sobra.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    for campo in ("exame-mais", "vizinho-mais"):
        achado = re.search(rf'<div class="ressalva" data-campo="{campo}"[^>]*>', html)
        assert achado, f"o desenho não tem onde dizer o `{campo}`"
        assert 'data-hef-alvo="html"' in achado.group(0), achado.group(0)
    assert ".ressalva:has(.nada){display:none}" in html, (
        "a folha perdeu a peça que esconde a linha sem conteúdo — os dois `+N` "
        "passariam a ocupar altura todo dia")


def test_o_veredito_continua_cego_para_a_calada(pacote, cena, mesa) -> None:
    """Nada se perdeu: a linha cinza não pinta o topo.

    Se o veredito passasse a contar as caladas, uma ordem dispensada prenderia o
    topo em laranja para sempre e o ⊘ voltaria a ser botão morto — a definição
    que `_veredito_do_exame` escreve.
    """
    mesa(cena, {})
    falando = pacote._veredito_do_exame(pacote._itens_da_tela())
    mesa(cena, _dispensa_a_primeira(cena))
    calada = pacote._veredito_do_exame(pacote._itens_da_tela())
    assert falando and calada, "o veredito veio vazio — o teste não mede nada"
    assert falando != calada, (
        "calar uma ordem não mudou o veredito do topo — o ⊘ deixou de fazer "
        "alguma coisa visível, que é a definição de botão morto")


# ---------------------------------------------------------------------------
# CONEXOES-LIGAR-TUDO-01 (06/09/2026) — as linhas do balde `LIGAR` desta aba
#
# As cinco daqui para baixo têm a mesma forma: **o dono existe no produto, com
# a frase ou o número prontos, e o HTML não tinha onde escrever**. Cada teste
# pergunta ao PRODUTO e compara com o DONO — nunca com uma segunda cópia da
# frase escrita aqui.
# ---------------------------------------------------------------------------
def _ctx_de_alvo(pacote, indice, quantos=2):
    """Um `Contexto` com `quantos` controles e o alvo de saída em `indice`.

    A MESA É MONTADA PELO PRODUTO (`mesa_viva.mesa_do_estado`), e não à mão: é
    ele que decide qual `uniq` vira `p1` — e a conversão que este teste mede é
    exatamente a que atravessa as duas ordens. Uma mesa digitada aqui casaria
    com o que o teste espera e nunca com o que o produto faz.
    """
    from hefesto_dualsense4unix.interface import mesa_viva
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # O `player_slot` DESCE com a posição e o `index` SOBE: é o cruzamento que
    # faz as duas ordens divergirem, e sem ele o teste passaria com a conversão
    # errada. **O CAMPO É `player_slot`, e não `player`** — quem decide a
    # identidade é `actions/base.numero_do_controle`, e ele lê o SLOT DE SESSÃO;
    # `player` responde outra pergunta ("está jogando agora, e como quem?") e é
    # `None` fora do co-op. Medido em 06/09/2026: com `player` a mesa saiu
    # `p1→index 0`, as duas ordens coincidiram e a mordida NÃO mordeu.
    controles = [
        {"uniq": f"aa:bb:cc:00:00:{n:02x}", "connected": True, "index": n,
         "transport": "usb", "player_slot": quantos - n}
        for n in range(quantos)
    ]
    estado = {"controllers": controles, "output_target_index": indice}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    return Contexto(state=estado, mesa=mesa, conectados=controles), mesa


def test_o_alvo_de_saida_e_lido_de_volta_do_daemon(pacote) -> None:
    """Ela clica "só este" no P2 e a tela passa a apontar para ele.

    O DEFEITO QUE ISTO FECHA: o gesto `alvo` escrevia `controller.target.set`, o
    daemon obedecia, e no tique seguinte o acordeão continuava aberto no P1 — o
    `checked` do desenho. A fita do topo junto, porque o destaque dela vem das
    regras `body:has(#gc-pN:checked)` do gerador.

    MORDE: devolva a leitura ao índice CRU (`lugares[indice + 1]`, sem passar
    pelo `uniq`) e este teste reprova — o daemon numera por posição em
    `controllers` e o desenho por posição na mesa ORDENADA POR IDENTIDADE, e
    aqui as duas estão trocadas de propósito.
    """
    ctx, mesa = _ctx_de_alvo(pacote, indice=0)
    # O `index: 0` é o `player: 2` desta cena, e o produto o põe em `p2`.
    esperado = next(m["pref"] for m in mesa
                    if m["uniq"] == ctx.state["controllers"][0]["uniq"])
    assert pacote._pref_do_alvo(ctx) == esperado, (
        f"o alvo `index: 0` virou {pacote._pref_do_alvo(ctx)!r} e o produto põe "
        f"aquele controle em {esperado!r} — as duas ordens foram confundidas")
    marcado = pacote._alvo_de_saida(ctx)
    lugares = [pacote.TODOS_NA_TELA, *sorted(pacote.TODOS_OS_LUGARES)]
    assert len(marcado) == len(lugares), marcado
    acesos = [onde for onde, v in zip(lugares, marcado, strict=True) if v == "sim"]
    assert acesos == [esperado], marcado


def test_o_alvo_todos_marca_o_primeiro_radio(pacote) -> None:
    """`index: null` é o broadcast, e ele marca o "todos" — nunca um controle.

    MORDE: trate o `None` como "não sei" e devolva a lista toda vazia; a tela
    fica sem afirmar nada onde o daemon disse, com todas as letras, que a saída
    vale para a mesa inteira.
    """
    ctx, _ = _ctx_de_alvo(pacote, indice=None)
    marcado = pacote._alvo_de_saida(ctx)
    assert marcado[0] == "sim", marcado
    assert not any(marcado[1:]), marcado


def test_um_alvo_que_o_estado_nao_traduz_nao_marca_nada(pacote) -> None:
    """Índice fora da lista desmarca os cinco — e isso NÃO é o "todos".

    A DIFERENÇA É O PONTO: marcar o "todos" afirmaria um broadcast que o daemon
    não disse; deixar os cinco vazios não afirma nada, que é o único estado
    honesto quando a conversão falha.

    MORDE: devolva `TODOS_NA_TELA` no ramo do não-traduzido e a primeira posição
    acende sobre um alvo que ninguém leu.
    """
    ctx, _ = _ctx_de_alvo(pacote, indice=97)
    assert pacote._pref_do_alvo(ctx) == ""
    assert not any(pacote._alvo_de_saida(ctx)), pacote._alvo_de_saida(ctx)


def test_a_lista_do_alvo_vai_em_todo_tique_inclusive_vazia(pacote) -> None:
    """Sem a chave `output_target_index` a lista sai VAZIA — e sai.

    É a regra do botão cinza da ONDA0-F: uma chave que só aparece quando há o
    que dizer deixa na tela a marca do tique anterior, e um acordeão preso no
    controle de antes é a tela mentindo sobre para onde a saída vai.

    A RÉGUA PASSA PELO `pacote()`, E NÃO PELO HELPER — 06/09/2026, e a primeira
    versão dela não provava nada: perguntar direto a `_alvo_de_saida` deixa a
    emissão de fora, que é justamente onde a chave pode sumir. A mordida que
    embrulhou a linha do `pacote()` num condicional passou VERDE por isso.

    MORDE: emita `alvo-aberto` só quando houver alvo e o `KeyError` aqui é a
    reprovação.
    """
    ctx, _ = _ctx_de_alvo(pacote, indice=0)
    ctx.state.pop("output_target_index")
    assert pacote._alvo_de_saida(ctx) == ["", "", "", "", ""]
    carga = pacote.pacote(ctx)
    assert "alvo-aberto" in carga, (
        "o pacote deixou de emitir `alvo-aberto` quando não há alvo — a tela "
        "fica com a marca do tique anterior, apontando o controle de antes")
    assert not any(carga["alvo-aberto"]), carga["alvo-aberto"]


def test_o_desenho_tem_um_endereco_por_radio_do_acordeao() -> None:
    """Os cinco `<input>` do acordeão têm o endereço, e só um nasce `checked`.

    A LISTA É DISTRIBUÍDA POR POSIÇÃO no DOM. Um rádio sem `data-campo` faria o
    valor do P1 cair no P2 e a tela apontar o controle errado — pior que o
    defeito que esta cura fecha.

    MORDE: tire o `data-campo` de um dos cinco e a contagem cai.
    """
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    quantos = html.count('data-campo="alvo-aberto" data-hef-alvo="marcado"')
    assert quantos == len(TODOS_OS_LUGARES) + 1, (
        f"são {quantos} rádios com endereço e a mesa tem "
        f"{len(TODOS_OS_LUGARES)} lugares mais o 'todos'")
    assert html.count('data-hef-alvo="marcado" checked') <= 1, (
        "o desenho afirma dois alvos de saída ao mesmo tempo")


def test_o_aviso_do_controle_nao_adotado_vem_do_dono(pacote) -> None:
    """A frase é `status_actions.texto_de_controle_nao_adotado`, palavra por palavra.

    MORDE: escreva a frase aqui no pacote e ela deixa de acompanhar o dono —
    que é quem sabe de quantos em quantos minutos o produto tenta sozinho
    (`MINUTOS_ENTRE_TENTATIVAS`, lido da unit do systemd).
    """
    from hefesto_dualsense4unix.app.actions.status_actions import (
        texto_de_controle_nao_adotado,
    )

    st = {"controles_sem_driver": {"quantidade": 2, "ids": ["x", "y"]}}
    assert pacote._frase_do_sem_driver(st) == texto_de_controle_nao_adotado(st)
    assert pacote._frase_do_sem_driver(st).strip(), "o dono não disse nada"


def test_sem_controle_orfao_a_linha_do_aviso_some(pacote) -> None:
    """Zero órfão vira `monta.NADA_A_DIZER`, e a folha esconde a linha.

    NUNCA `""`: o `escrever()` do piloto troca vazio por travessão ANTES de
    olhar o alvo, e a tela ganharia uma linha com um `—` — altura para não
    dizer nada.

    MORDE: devolva `""` no ramo vazio e a asserção do marcador cai.
    """
    nada = str(pacote._monta().NADA_A_DIZER)
    assert pacote._frase_do_sem_driver({}) == nada
    assert pacote._frase_do_sem_driver(
        {"controles_sem_driver": {"quantidade": 0, "ids": []}}) == nada


def test_o_aviso_do_radio_fragil_nomeia_os_controles(pacote) -> None:
    """O aviso do Bluetooth nativo frágil sai do dono, COM os números.

    A REGRA DOS DOIS DONOS É DELES: `controles_bt_frageis` lê a lista publicada
    e `texto_native_bt_fragil` a vira frase — e lista vazia com o booleano ACESO
    quer dizer *"não sei quais"*, não *"nenhum"*. O aviso acende sem nomes.

    MORDE: acenda a linha pelo tamanho da lista (`if not numeros: return nada`)
    e o segundo caso reprova — o aviso cala com o daemon dizendo que há frágil.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        NATIVE_BT_FRAGIL_TEXT,
        texto_native_bt_fragil,
    )

    st = {"native_bt_fragil": True, "native_bt_fragil_controles": [2, 3]}
    assert pacote._frase_do_radio_fragil(st) == texto_native_bt_fragil([2, 3])
    assert "2" in pacote._frase_do_radio_fragil(st)
    sem_nomes = {"native_bt_fragil": True, "native_bt_fragil_controles": []}
    assert pacote._frase_do_radio_fragil(sem_nomes) == NATIVE_BT_FRAGIL_TEXT


def test_sem_radio_fragil_a_linha_some(pacote) -> None:
    """Booleano apagado é silêncio — e o silêncio não ocupa pixel.

    MORDE: tire a guarda do `native_bt_fragil` e o aviso acende em toda mesa que
    não publique a chave, que é o alarme sem medição que ela baniu.
    """
    nada = str(pacote._monta().NADA_A_DIZER)
    assert pacote._frase_do_radio_fragil({}) == nada
    assert pacote._frase_do_radio_fragil({"native_bt_fragil": False}) == nada


def test_as_quatro_ressalvas_novas_tem_endereco_na_pagina() -> None:
    """As quatro linhas existem no desenho, com o alvo `html`.

    A RÉGUA COBRA O ENDEREÇO, não a frase: a frase é do dono e muda quando ele
    mudar; o que não pode sumir é o lugar onde ela cabe. Endereço que some é
    campo que o piloto não acha e escreve zero — calado, que é como os quatro
    viviam até hoje.

    MORDE: tire uma das quatro do gerador, regere, e a linha dela cai aqui.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    for campo in ("sem-driver", "radio-fragil", "hub-em-comum",
                  "gabinete-contagens"):
        achado = re.search(rf'<div class="ressalva" data-campo="{campo}"[^>]*>', html)
        assert achado, f"o desenho não tem onde dizer o `{campo}`"
        assert 'data-hef-alvo="html"' in achado.group(0), achado.group(0)


def test_o_hub_em_comum_e_as_contagens_saem_dos_donos(pacote) -> None:
    """As duas frases são de `secao_mesa`, e o produto NÃO escolhe entre elas.

    A REGRA DAS CONTAGENS É A QUE MAIS IMPORTA: o que o firmware conta e o que o
    kernel conta vão os DOIS, lado a lado. Escolher um desenharia um gabinete
    que ninguém tem, e ela procuraria na traseira buracos que o mapa não mostra.

    MORDE: faça `_frases_do_gabinete` devolver só a primeira linha e a segunda
    asserção cai; troque o `<br>` por um espaço e a terceira cai.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
        _linhas_do_gabinete,
    )

    gabinete = {
        "contagens": {
            "firmware": {"valor": 5, "de_onde_sei": "lido-do-firmware"},
            "kernel_buracos": {"valor": 15, "de_onde_sei": "lido-do-kernel"},
        }
    }
    esperadas = [f for f in _linhas_do_gabinete(gabinete) if f]
    assert len(esperadas) >= 2, "o dono não deu as duas contagens — a cena mudou"
    antes = pacote._GABINETE
    try:
        pacote._GABINETE = gabinete
        saiu = pacote._frases_do_gabinete()
    finally:
        pacote._GABINETE = antes
    for frase in esperadas:
        assert frase in saiu, f"a linha do gabinete perdeu {frase!r}"
    assert saiu.count("<br>") == len(esperadas) - 1, saiu


def test_sem_gabinete_json_a_linha_das_contagens_some(pacote) -> None:
    """Primeira instalação não tem `gabinete.json`, e a linha não nasce.

    Firmware é FONTE, nunca premissa — e uma linha que só sabe dizer "não sei"
    ocupa a largura que esta aba não tem.

    MORDE: devolva `""` em vez do marcador e a linha passa a ocupar altura com
    um travessão dentro.
    """
    nada = str(pacote._monta().NADA_A_DIZER)
    antes = pacote._GABINETE
    try:
        pacote._GABINETE = {}
        assert pacote._frases_do_gabinete() == nada
    finally:
        pacote._GABINETE = antes


def test_a_regua_do_radio_recebe_a_chave_crua_do_transporte(pacote) -> None:
    """`_da_mesa_para_a_regua` carrega `transporte`, e sem ele a régua zera.

    O DEFEITO MEDIDO (06/09/2026): a costura da ONDA B trocou o
    `c["via"] == "BT"` de `_regua_do_radio` por `_e_radio(c)`, e o `c` de lá é o
    dicionário que esta função devolve — que **nunca carregou `transporte`**.
    `no_radio` ficava sempre vazio, e a régua de Desempenho mostrava ZERO
    controle no rádio com o controle no rádio. É o sintoma exato que o
    comentário da troca dizia estar prevenindo.

    MORDE: tire a chave `transporte` do dicionário e `_e_radio` responde `False`
    sobre um controle que está no rádio.
    """
    m = {"jogador": 2, "nome": "Galactic Purple", "via": "rádio",
         "transporte": "bt", "cor": "galactic-purple", "uniq": "aa:bb:cc:00:00:02"}
    saiu = pacote._da_mesa_para_a_regua(m, set())
    assert pacote._e_radio(saiu), (
        "a régua do rádio não reconhece o controle que está NO rádio — a chave "
        "crua não viajou junto com a palavra")
    assert saiu["via"] == "rádio", "a palavra da tela se perdeu no caminho"
