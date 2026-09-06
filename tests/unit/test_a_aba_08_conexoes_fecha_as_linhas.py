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
