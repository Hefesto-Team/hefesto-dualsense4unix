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
    """E a frase nova é a do DONO desta aba, lida no ato."""
    from hefesto_dualsense4unix.interface import aba08, onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert aba08.MAPA_JA_GRAVOU in html


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
