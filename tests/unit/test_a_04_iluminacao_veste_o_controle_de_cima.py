"""A `04-iluminacao` mostra o controle DA MESA, e nunca o do desenho.

A LEI, e ela é dela (03/09/2026)::

    "se no topo tá mostrando controle white player 1, então cada aba vai usar os
    controles lá de cima. Não mistura com a info dos mockups. Cada feature faz
    referencia ao controle conectado. Por isso temos o mapa pra servir como  (noqa-acento)
    variável de identificação"

    (A frase é dela, palavra por palavra: citação não se corrige.)

E, sobre a COR: *"se identificou o controle como modelo White a cor do card em
volta tem que ser branco. Temos isso no mapa."*

O QUE ESTAVA NA TELA DELA, fotografado em 03/09/2026 com dois controles na mesa
(um White no cabo, um por rádio sem cor lida)::

    rótulo da coluna (VIVO)    P1 • White • USB
    moldura em volta (CRAVADA) vermelha — o Cosmic Red do mockup

A moldura é como esta aba diz de quem é a luz (`D-A-BORDA-E-A-IDENTIDADE-DA-PECA`),
e ela estava dizendo o nome de um controle que não estava na mesa. Era a maior
das 39 identidades congeladas da bancada desta aba — e as outras 33 estão aqui
também: as dicas que nomeavam o controle do desenho e o antes/depois do rodapé.

O QUE ESTES TESTES COBREM, e cada um tem a mordida escrita:

1. a moldura tem endereço e NÃO tem `--plastico` cravado;
2. o pacote MANDA a cor da casca, lida da mesa viva;
3. sem cor lida ele manda VAZIO — regra dela: campo sem informação não mostra
   nada. Um `#000` ali diria PRETO, que é uma cor;
4. o anelzinho do dono declara de quem é, senão a régua o lê como congelado;
5. o antes/depois do rodapé é um `blocos:` vivo e nomeia quem está na mesa;
6. nenhuma dica do MIOLO nomeia um controle — `title` é atributo, e o piloto não
   tem alvo para atributo: o que se escrever ali fica congelado para sempre.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


#: A MESA DELA DE 03/09/2026, na forma que `mesa_viva.mesa_do_estado` devolve: um
#: White no cabo e um por rádio cuja COR NÃO FOI LIDA — que é o estado real na
#: ponta de `dev`, porque a leitura de cor por rádio ainda não chegou.
#: MAC da faixa sintética da casa: há dois portões de anonimato nesta árvore.
MESA_DELA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
    {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "jogador": 2, "cor": "",
     "nome": "Não sei", "via": "BT", "transporte": "bt"},
]

NO_CABO = {"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "connected": True,
           "player": 1, "player_slot": 1, "is_primary": True,
           "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
           "lightbar_source": "sysfs", "battery_pct": 95}
NO_RADIO = {"uniq": "aa:bb:cc:00:00:02", "transport": "bt", "connected": True,
            "player": 2, "player_slot": 2, "is_primary": False,
            "lightbar_rgb": [255, 0, 0], "lightbar_on": True,
            "lightbar_source": "sysfs", "battery_pct": 85}

#: O hex da casca White, LIDO do dono (`monta.cor_da_zona`) e não digitado — se
#: a amostragem mudar, o teste acompanha. Digitá-lo aqui criaria a segunda
#: verdade que o `cores-do-dualsense.csv` existe para matar.
BRANCO = "#e4e0d8"


@pytest.fixture
def carga():
    """O pacote da `04`, com a mesa DELA."""
    import pacotes

    def montar(mesa=None, conectados=None):
        ctx = pacotes.Contexto(
            state={"active_profile": ""},
            mesa=list(mesa if mesa is not None else MESA_DELA),
            conectados=list(conectados if conectados is not None
                            else [NO_CABO, NO_RADIO]),
            estados={})
        return pacotes.pacote_da_pagina("04-iluminacao.html", ctx)

    return montar


@pytest.fixture
def bancada():
    """O HTML da bancada — o desenho de HOJE, que é o que ela olha."""
    import onde

    return onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")


def _miolo(doc: str) -> str:
    """Só o que a JANELA mostra, sem comentário HTML e sem a legenda do rodapé.

    O corte é o mesmo do `aba04._conferir`, e pela mesma razão medida: a régua da
    Jogar nasceu errada duas vezes por casar um token dentro do comentário que o
    explicava.
    """
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    return re.sub(r"<!--.*?-->", "", corpo, flags=re.S)


# ---------------------------------------------------------------------------
# 1. a moldura — a cor que ela mandou vir do aparelho
# ---------------------------------------------------------------------------
def test_a_moldura_tem_endereco_e_nao_tem_cor_cravada(bancada):
    """A borda do desenho deixou de ser a cor do mockup.

    O `--plastico:#hex` no `style` da moldura era a cor do DESENHO, e nada a
    reescrevia: nenhum alvo do pintor escreve variável CSS. A cura é a folha ler
    `currentColor` e o pacote mandar a cor pelo alvo `cor`.

    A MORDIDA: devolva `style="--plastico:{cor_da_zona(...)}"` ao `coluna()` do
    `aba04.py`, rode o gerador, e as duas asserções reprovam — a primeira porque
    o endereço some, a segunda porque a cor cravada volta.
    """
    corpo = _miolo(bancada)
    assert corpo.count('class="moldura" data-campo="plastico" data-hef-alvo="cor"') == 2, (
        "a moldura das duas colunas conectadas perdeu o endereço da cor do "
        "plástico — sem ele a borda fica na cor que o gerador cravou.")
    molduras = re.findall(r'<div class="moldura"[^>]*>', corpo)
    cravadas = [m for m in molduras if "--plastico" in m]
    assert not cravadas, (
        f"a cor do plástico voltou a ser cravada na moldura: {cravadas}. "
        f"O que está escrito ali é o controle do MOCKUP, e é o que a tela dela "
        f"mostrava em volta de um controle branco.")


def test_a_folha_le_a_borda_de_currentcolor_e_o_desenho_nao_herda(bancada):
    """As duas metades da cura, e uma sem a outra estraga a tela.

    Sem `currentColor` na borda, o alvo `cor` escreve e nada muda. Sem pinar a
    cor do `.ds-svg`, a cor que vai à borda TINGE os glifos que desenham com
    `stroke="currentColor"` e não têm classe — o PS, o share, o options, o mic e
    os analógicos. Medido no Chrome, dentro desta página, em 03/09/2026.

    A MORDIDA: tire `.luz-grade .moldura .ds-svg{color:var(--fg)}` do CSS e
    a segunda asserção reprova.
    """
    assert ".luz-grade .moldura{color:var(--linha);border:1px solid currentColor;" in bancada, (
        "a borda voltou a sair de `--plastico`: o alvo `cor` do pintor escreve "
        "`style.color`, e nenhum alvo dele escreve variável CSS.")
    assert ".luz-grade .moldura .ds-svg{color:var(--fg)}" in bancada, (
        "o desenho voltou a herdar a cor da moldura — os glifos sem classe "
        "(`glifo-ps`, `glifo-share`, `glifo-options`, `glifo-mic`, os "
        "analógicos) desenham com `stroke=\"currentColor\"`.")


def test_o_pacote_manda_a_cor_da_casca_do_controle_da_mesa(carga):
    """O White dela chega à coluna como `#e4e0d8`.

    A MORDIDA: troque `casa.get("cor")` por `""` no pacote e esta linha reprova
    com vazio — que é a tela de novo sem cor nenhuma.
    """
    import monta

    col = carga()["colunas"][NO_CABO["uniq"]]
    assert col["plastico"] == monta.cor_da_zona("white") == BRANCO, (
        f"a coluna do controle branco mandou {col['plastico']!r}. O dono do hex "
        f"é `monta.cor_da_zona`, que LÊ a folha que pinta o desenho.")
    assert col["identidade"] == "P1 • White • USB", (
        "o rótulo e a cor da moldura têm de falar do MESMO controle.")


def test_sem_cor_lida_o_pacote_manda_vazio_e_nunca_a_do_mockup(carga):
    """Campo sem informação não mostra nada — a regra é dela.

    A cor do plástico chega pelo broker, uma vez por endereço e em thread; o
    controle por RÁDIO na ponta de `dev` chega sem ela. O honesto é a moldura
    ficar neutra, e nunca cair de volta no desenho.

    A MORDIDA: faça `_cor_do_plastico("")` devolver `cor_da_zona("cosmic-red")`
    e esta linha reprova — que é exatamente a queda que a lei dela proíbe.
    """
    col = carga()["colunas"][NO_RADIO["uniq"]]
    assert col["plastico"] == "", (
        f"o controle de rádio, sem cor lida, mandou {col['plastico']!r}. "
        f"Um hex ali é uma cor inventada; o alvo `cor` com vazio devolve a "
        f"borda ao neutro da folha.")


def test_a_coluna_nunca_manda_a_cor_de_um_controle_que_nao_e_o_dela(carga):
    """Duas colunas, dois valores — e o do rádio não herda o do cabo."""
    colunas = carga()["colunas"]
    assert colunas[NO_CABO["uniq"]]["plastico"] != colunas[NO_RADIO["uniq"]]["plastico"]


# ---------------------------------------------------------------------------
# 2. o anelzinho do dono — o congelado que mora dentro de um bloco vivo
# ---------------------------------------------------------------------------
def test_o_anel_do_dono_declara_de_quem_e():
    """O `<i class="dono">` carrega `--plastico` e mora num bloco reescrito.

    A régua da identidade julga o `--plastico` no elemento que o carrega — de
    propósito, porque *"um pai endereçado não dá ao filho o direito de trazer cor
    congelada"*. A exceção é esta: o pai não dá direito, ele REESCREVE o filho
    (`data-campo="players" data-hef-alvo="html"`), e o endereço é a única forma
    de dizer isso no HTML.

    A MORDIDA: tire o `data-hef` de `um_botao_de_player` e esta linha reprova.
    """
    from pacotes import a04_iluminacao as pac

    botao = pac.um_botao_de_player(
        "White", 1, 2, {"nome": "Não sei", "via": "BT", "cor": ""})
    assert 'class="dono"' not in botao, (
        "um dono SEM cor lida não pode desenhar anel — seria inventar a casca.")
    com_cor = pac.um_botao_de_player(
        "Não sei", 2, 1, {"nome": "White", "via": "USB", "cor": "white"})
    assert f'data-hef="{pac.ANEL_DO_DONO}"' in com_cor, (
        "o anel perdeu o endereço: a régua da identidade volta a contá-lo como "
        "cor congelada, em todas as colunas.")
    assert BRANCO in com_cor, "o anel do dono perdeu a cor da casca dele."


def test_o_anel_nao_repete_o_endereco_da_fileira():
    """Um nome próprio, e nunca `players`.

    O pintor acha por `querySelectorAll`, então um `<i>` que repetisse `players`
    receberia a fileira INTEIRA como `innerHTML` — quatro botões dentro de um
    anelzinho, a cada tique.
    """
    from pacotes import a04_iluminacao as pac

    assert pac.ANEL_DO_DONO != "players"
    assert pac.ANEL_DO_DONO.startswith("players."), (
        "o nome do anel deixou de dizer a que bloco ele pertence.")


# ---------------------------------------------------------------------------
# 3. o antes/depois do rodapé — um `blocos:` vivo
# ---------------------------------------------------------------------------
def test_o_antes_e_depois_nomeia_quem_esta_na_mesa(carga):
    """O exemplo da troca é o caso REAL dela, com os controles REAIS.

    Ele era escrito com a `MESA` do desenho — dois nomes de mockup num rodapé
    que o produto renderiza, e dezesseis `--plastico` cravados.

    A MORDIDA: troque `secao_da_troca(ctx.mesa)` por `secao_da_troca(monta.MESA)`
    no pacote e as duas primeiras asserções reprovam, nomeando o mockup.
    """
    from pacotes import a04_iluminacao as pac

    html = carga()["blocos"][pac.SECAO_DA_TROCA]
    assert "White" in html, "o antes/depois não fala do controle que está na mesa."
    for do_mockup in ("Cosmic Red", "Starlight Blue", "Galactic Purple"):
        assert do_mockup not in html, (
            f"o antes/depois do rodapé ainda nomeia {do_mockup!r} — um controle "
            f"que não está na mesa dela.")
    # A permutação: o P1 vira P2 e o P2 vira P1, e ninguém mais se mexe.
    assert html.count('class="troca-item') == 4, (
        "o antes e o depois têm de mostrar os DOIS controles, nas duas linhas.")
    assert 'data-hef="troca.item"' in html, (
        "os itens perderam o endereço — a régua volta a ler o `--plastico` "
        "deles como cor congelada.")


def test_a_troca_precisa_de_dois_e_diz_isso_em_vez_de_inventar(carga):
    """Com um controle só não há troca — e a seção fala, em vez de mentir.

    A MORDIDA: apague o `if len(ordenada) < 2` de `secao_da_troca` e a função
    levanta `IndexError` no primeiro tique de uma mesa com um controle — que é
    a mesa dela toda vez que ela desliga um.
    """
    from pacotes import a04_iluminacao as pac

    html = carga(mesa=MESA_DELA[:1], conectados=[NO_CABO])["blocos"][pac.SECAO_DA_TROCA]
    assert "um controle só" in html
    assert 'class="troca-item' not in html, (
        "com um controle na mesa a seção desenhou um segundo — é a frase que "
        "nomeia um controle que não está lá, pela nona vez nesta casa.")
    vazia = pac.secao_da_troca([])
    assert "nenhum controle" in vazia


def test_a_bancada_tem_onde_pousar_o_antes_e_depois(bancada):
    """O `blocos:` pousa por `document.querySelector` — sem o contêiner, nada.

    A MORDIDA: tire o `<div class="nota-troca" data-hef="troca">` do `LEGENDA`,
    rode o gerador, e esta linha reprova. Sem ele o pacote emitiria a seção viva
    a cada tique e o rodapé continuaria com o texto do mockup, calado.
    """
    from pacotes import a04_iluminacao as pac

    assert '<div class="nota-troca" data-hef="troca">' in bancada
    assert pac.SECAO_DA_TROCA == ".nota-troca"
    assert pac.TITULO_DA_TROCA in bancada


def test_o_gerador_e_o_produto_desenham_a_mesma_secao_de_troca(bancada):
    """Um dono, dois chamadores — e é o que impede os dois lados de divergirem.

    É a mesma régua que já vale para a fileira de players e para o desenho da
    luz. Enquanto fossem duas escritas, o desenho e o produto podiam divergir
    sem ninguém ver — que foi como a `novo-layout/` divergiu 25 KB calada.
    """
    import monta
    from pacotes import a04_iluminacao as pac

    assert pac.secao_da_troca(monta.MESA, recuo="    ") in bancada, (
        "o rodapé da bancada deixou de sair de `secao_da_troca` — há uma "
        "segunda escrita da mesma seção.")


# ---------------------------------------------------------------------------
# 4. as dicas — `title` é atributo, e atributo o pintor não alcança
# ---------------------------------------------------------------------------
#: Os nomes que a mesa do DESENHO usa. Eles são os que apareciam nas dicas —
#: lidos de `monta.MESA` e não digitados, para que uma mesa de desenho nova não
#: deixe este teste medindo o vazio.
def _nomes_do_desenho() -> list[str]:
    import monta

    return sorted({str(c["nome"]) for c in monta.MESA})


@pytest.mark.parametrize("nome", _nomes_do_desenho())
def test_nenhuma_dica_congelada_do_miolo_nomeia_um_controle(bancada, nome):
    """O `title` fica no que o gerador soube, e o gerador só sabe o mockup.

    O piloto pinta `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e
    `cor` — e nenhum deles escreve atributo. Toda frase escrita num `title` do
    miolo é congelada PARA SEMPRE, mesmo num elemento que já tem endereço: a
    régua da identidade nem a acusa nesse caso, porque ela pula o `title` de
    quem já tem endereço. Era assim que os oito botões de cor diziam *"pinta a
    barra do Cosmic Red"* na coluna de um controle branco.

    O QUE SOBRA SÃO OS `title` DENTRO DE BLOCO VIVO — a fileira de players e o
    desenho da luz —, e esses o pacote reescreve a cada tique.

    A MORDIDA: devolva `do {c["nome"]}` ao `title` do "Desligar" ou dos oito
    tons, rode o gerador, e este teste reprova nomeando o arquivo.
    """
    corpo = _miolo(bancada)
    # Os dois blocos que o produto TROCA INTEIROS saem da conta: o que está
    # dentro deles é semente, e o pacote a reescreve com a mesa viva.
    for marca in ('data-campo="players" data-hef-alvo="html"',
                  'data-campo="luz" data-hef-alvo="html"'):
        while marca in corpo:
            i = corpo.index(marca)
            fim = corpo.index("</div>", i)
            corpo = corpo[:i] + corpo[fim:]
    dicas = re.findall(r'title="([^"]*)"', corpo)
    culpadas = [d for d in dicas if nome in d]
    assert not culpadas, (
        f"{len(culpadas)} dica(s) congelada(s) do miolo nomeiam {nome!r}, que é "
        f"um controle do DESENHO: {culpadas[:2]}. `title` é atributo e o piloto "
        f"não tem alvo para atributo — o que está escrito ali fica na tela dela.")


def test_a_dica_do_jogador_diz_a_regra_e_nao_o_exemplo(bancada):
    """A coluna de RÓTULOS é uma só para as quatro — não há a quem endereçar.

    A dica dizia *"pôr o Starlight Blue no 1 faz o Cosmic Red virar 2"*: dois
    nomes do mockup num texto que vale para as quatro colunas. Aqui a cura não
    é endereço, é dizer a REGRA em vez do exemplo — quem nomeia os dois de
    verdade é a dica de cada botão da fileira, que o pacote reescreve.

    A MORDIDA: devolva os dois `{...["nome"]}` à dica e esta linha reprova.
    """
    corpo = _miolo(bancada)
    assert "quem tem aquele número hoje fica com o deste" in corpo
    assert "faz o\n" not in corpo.split("Dar a este controle", 1)[-1][:400]
