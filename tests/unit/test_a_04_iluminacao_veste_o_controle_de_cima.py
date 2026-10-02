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
    """Só o que a JANELA mostra, sem comentário HTML e sem a legenda do rodapé."""
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    return re.sub(r"<!--.*?-->", "", corpo, flags=re.S)


def test_a_moldura_tem_endereco_e_nao_tem_cor_cravada(bancada):
    """A borda do desenho deixou de ser a cor do mockup.

    O `--plastico:#hex` no `style` da moldura era a cor do DESENHO, e nada a
    reescrevia: nenhum alvo do pintor escreve variável CSS. A cura é a folha ler
    `currentColor` e o pacote mandar a cor pelo alvo `cor`.

    E SÃO AS QUATRO MOLDURAS desde 07/09/2026, não as duas conectadas. Esta
    conta dizia `== 2`, e assim **media o defeito**: o lugar que nascia vazio  (noqa-acento)
    saía sem endereço nenhum, e a moldura do P3 que chegasse depois ficaria no
    cinza para sempre — o dado dela chegando sem onde pousar. O `style` com a
    cor CRAVADA continua só nos conectados, e é a segunda asserção que o cobra:
    endereço nos quatro, valor só em quem tem aparelho.

    A MORDIDA: devolva `style="--plastico:{cor_da_zona(...)}"` ao `coluna()` do
    `aba04.py`, rode o gerador, e as duas asserções reprovam — a primeira porque
    o endereço some, a segunda porque a cor cravada volta.
    """
    import monta

    corpo = _miolo(bancada)
    endereco = 'class="moldura" data-campo="plastico" data-hef-alvo="cor"'
    assert corpo.count(endereco) == len(monta.MESA), (
        "alguma moldura da grade perdeu o endereço da cor do plástico — sem "
        "ele a borda fica na cor que o gerador cravou, e o lugar que ganha um "
        "controle fica no cinza.")
    molduras = re.findall(r'<div class="moldura"[^>]*>', corpo)
    cravadas = [m for m in molduras if "--plastico" in m]
    assert not cravadas, (
        f"a cor do plástico voltou a ser cravada na moldura: {cravadas}. "
        f"O que está escrito ali é o controle do MOCKUP, e é o que a tela dela "
        f"mostrava em volta de um controle branco.")


def test_a_folha_le_a_borda_de_currentcolor_e_o_desenho_nao_herda(bancada):
    """As duas metades da cura, e uma sem a outra estraga a tela."""
    assert ".luz-grade .moldura{color:var(--linha);border:1px solid currentColor;" in bancada, (
        "a borda voltou a sair de `--plastico`: o alvo `cor` do pintor escreve "
        "`style.color`, e nenhum alvo dele escreve variável CSS.")
    assert ".luz-grade .moldura .ds-svg{color:var(--fg)}" in bancada, (
        "o desenho voltou a herdar a cor da moldura — os glifos sem classe "
        "(`glifo-ps`, `glifo-share`, `glifo-options`, `glifo-mic`, os "
        "analógicos) desenham com `stroke=\"currentColor\"`.")


def test_o_pacote_manda_a_cor_da_casca_do_controle_da_mesa(carga):
    """O White dela chega à coluna como `#e4e0d8`."""
    import monta

    col = carga()["colunas"][NO_CABO["uniq"]]
    assert col["plastico"] == monta.cor_da_zona("white") == BRANCO, (
        f"a coluna do controle branco mandou {col['plastico']!r}. O dono do hex "
        f"é `monta.cor_da_zona`, que LÊ a folha que pinta o desenho.")
    assert col["identidade"] == "P1 • White • USB", (
        "o rótulo e a cor da moldura têm de falar do MESMO controle.")


def test_sem_cor_lida_o_pacote_manda_vazio_e_nunca_a_do_mockup(carga):
    """Campo sem informação não mostra nada — a regra é dela."""
    col = carga()["colunas"][NO_RADIO["uniq"]]
    assert col["plastico"] == "", (
        f"o controle de rádio, sem cor lida, mandou {col['plastico']!r}. "
        f"Um hex ali é uma cor inventada; o alvo `cor` com vazio devolve a "
        f"borda ao neutro da folha.")


def test_a_coluna_nunca_manda_a_cor_de_um_controle_que_nao_e_o_dela(carga):
    """Duas colunas, dois valores — e o do rádio não herda o do cabo."""
    colunas = carga()["colunas"]
    assert colunas[NO_CABO["uniq"]]["plastico"] != colunas[NO_RADIO["uniq"]]["plastico"]


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
        "White", 1, 2, {"nome": "Não sei", "via": "BT", "cor": ""}, quantos=2)
    assert 'class="dono"' not in botao, (
        "um dono SEM cor lida não pode desenhar anel — seria inventar a casca.")
    com_cor = pac.um_botao_de_player(
        "Não sei", 2, 1, {"nome": "White", "via": "USB", "cor": "white"}, quantos=2)
    assert f'data-hef="{pac.endereco_do_anel(1)}"' in com_cor, (
        "o anel perdeu o endereço: a régua da identidade volta a contá-lo como "
        "cor congelada, em todas as colunas.")
    assert f'data-hef-alvo="{pac.ALVO_DO_PLASTICO}"' in com_cor, (
        "o anel tem endereço e não diz o ALVO — o pintor cairia no padrão e "
        "escreveria a cor como TEXTO dentro do `<i>`.")
    assert BRANCO in com_cor, "o anel do dono perdeu a cor da casca dele."


def test_o_anel_nao_repete_o_endereco_da_fileira():
    """Um nome próprio, e nunca `players`."""
    from pacotes import a04_iluminacao as pac

    assert pac.ANEL_DO_DONO != "players"
    assert pac.ANEL_DO_DONO.startswith("players."), (
        "o nome do anel deixou de dizer a que bloco ele pertence.")


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
    assert html.count('class="troca-item') == 4, (
        "o antes e o depois têm de mostrar os DOIS controles, nas duas linhas.")
    assert 'data-hef="troca.item"' in html, (
        "os itens perderam o endereço — a régua volta a ler o `--plastico` "
        "deles como cor congelada.")


def test_a_troca_precisa_de_dois_e_diz_isso_em_vez_de_inventar(carga):
    """Com um controle só não há troca — e a seção fala, em vez de mentir."""
    from pacotes import a04_iluminacao as pac

    html = carga(mesa=MESA_DELA[:1], conectados=[NO_CABO])["blocos"][pac.SECAO_DA_TROCA]
    assert "um controle só" in html
    assert 'class="troca-item' not in html, (
        "com um controle na mesa a seção desenhou um segundo — é a frase que "
        "nomeia um controle que não está lá, pela nona vez nesta casa.")
    vazia = pac.secao_da_troca([])
    assert "nenhum controle" in vazia


def test_a_bancada_tem_onde_pousar_o_antes_e_depois(bancada):
    """O `blocos:` pousa por `document.querySelector` — sem o contêiner, nada."""
    from pacotes import a04_iluminacao as pac

    assert '<div class="nota-troca" data-hef="troca">' in bancada
    assert pac.SECAO_DA_TROCA == ".nota-troca"
    assert pac.TITULO_DA_TROCA in bancada


def test_o_gerador_e_o_produto_desenham_a_mesma_secao_de_troca(bancada):
    """Um dono, dois chamadores — e é o que impede os dois lados de divergirem."""
    import monta
    from pacotes import a04_iluminacao as pac

    assert pac.secao_da_troca(monta.MESA, recuo="    ") in bancada, (
        "o rodapé da bancada deixou de sair de `secao_da_troca` — há uma "
        "segunda escrita da mesma seção.")


def _nomes_do_desenho() -> list[str]:
    import monta

    return sorted({str(c["nome"]) for c in monta.MESA})


@pytest.mark.parametrize("nome", _nomes_do_desenho())
def test_nenhuma_dica_congelada_do_miolo_nomeia_um_controle(bancada, nome):
    """O `title` fica no que o gerador soube, e o gerador só sabe o mockup."""
    corpo = _miolo(bancada)
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
    """A coluna de RÓTULOS é uma só para as quatro — não há a quem endereçar."""
    corpo = _miolo(bancada)
    dica = corpo.split("o número do jogador a este controle", 1)[-1][:600]
    assert "os dois trocarem" in dica, (
        "a dica do Jogador parou de dizer a REGRA da troca — sem ela, a pessoa "
        "clica um número de outro sem saber o que vai acontecer")
    nomeados = [nome for nome in _nomes_do_desenho() if nome in dica]
    assert not nomeados, (
        f"a dica do Jogador voltou a nomear {nomeados}: são controles do "
        f"DESENHO, numa coluna de rótulos que vale para as quatro colunas")
