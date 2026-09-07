#!/usr/bin/env python3
"""A ABA CONEXÕES PARA DE AFIRMAR O QUE NÃO MEDIU — `MIGRA-08-01`, 03/09/2026.

Quatro coisas na tela dela eram o DESENHO apresentado como diagnóstico da
máquina dela. Fotografadas no produto vivo, com dois controles ligados:

    o que a tela dizia                          o que a máquina diz
    ------------------------------------------  ---------------------------
    "Mova o adaptador Bluetooth da Entrada 3     `dongle_atras_de_hub` e
     para a Entrada 9", com de→para e ganho      `teclado_so_no_hub` — duas
                                                 ordens, nenhuma sobre a
                                                 Entrada 3 nem a 9
    duas das cinco linhas do Check-up VAZIAS     as cinco conferências
     (o tique roda três; `busctl` não cabe        respondem, e mais duas
      nele)                                       ordens acusam
    os três botões da VISADA apagados            `linha_de_visada='com_gente'`
    "Bateria 100%" e "Bateria 64%"               o que o daemon publicar

A CURA É PONTE, e o inventário é este — quatro donos que já existiam e que o
produto não chamava:

    `secao_exame.reexaminar` / `app.py:1180`   o exame COMPLETO ao ENTRAR na aba
    `gui.aba_conexoes.texto_da_contagem`       "2 controles • 1 no cabo • 1 no rádio"
    `gui.aba_conexoes.Controle.texto_da_bateria`  o `%` e o travessão
    `secao_mesa._linha_declarada:671`          pré-selecionar o que ela gravou
    `secao_exame._desenhar_o_que_fazer`        as ordens vêm antes das conferências

O QUINTO DONO ESTAVA QUEBRADO, e o teste
`test_o_dono_ainda_nao_desenha_a_ordem_da_mesa` é a catraca disso — ver o
docstring dele.

A MORDIDA, medida em 03/09/2026 (cada arranque foi devolvido por `cp`):

* troque `_html_da_ordem` por `return ""` →
  `test_a_ordem_de_servico_e_da_maquina_dela` reprova;
* devolva `_sala_na_tela` para `return {}` →
  `test_a_sala_pinta_o_que_ela_ja_declarou` reprova;
* tire o `sorted(...)` do fim de `_itens_da_tela` →
  `test_as_ordens_vem_antes_das_conferencias` reprova;
* devolva `"bateria": c.get("battery_pct")` cru →
  `test_a_bateria_sem_leitura_vira_o_travessao_do_produto` reprova;
* apague os `data-campo` novos do `aba08.py` e regenere →
  `test_o_desenho_tem_endereco_para_os_cinco` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"

#: A FRASE CRAVADA NO MOCKUP. Ela é a régua desta leva: enquanto ela puder sair
#: na tela sobre uma máquina que não tem Entrada 3 nem Entrada 9, a aba está
#: afirmando o que não mediu.
FRASE_DO_MOCKUP = "Mova o adaptador Bluetooth da Entrada 3 para a Entrada 9"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _uma_ordem(acao: str = "Leve o adaptador para uma entrada do computador.",
               destino: str = ""):  # type: ignore[no-untyped-def]
    """Uma `Ordem` do produto, montada com os campos que ela TEM.

    Os selos são os do dono (`ordens_da_mesa.SELOS`); montar a ordem à mão aqui
    é o que faz este teste medir o DESENHO do card e não a varredura do
    barramento, que depende da máquina de quem roda.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        MEDIDO_AQUI,
        Identidade,
        Linha,
        Ordem,
    )

    return Ordem(
        chave="prova_do_card",
        acao=acao,
        o_que_eu_vi=Linha(texto="2 de 3 adaptadores chegam por dentro de um hub.",
                          selo=MEDIDO_AQUI),
        por_que_importa=Linha(texto="Tudo que passa pelo hub divide o caminho.",
                              selo=MEDIDO_AQUI),
        ganho_esperado=Linha(texto="Não medi o ganho nesta máquina.",
                             selo=DERIVADO_DA_CONTA),
        alvo=Identidade(vid="2357", pid="0604", caminho="3-1.2"),
        arranjo="3-1.2 3-1.4",
        destino=destino,
    )


class _MesaFalsa:
    def __init__(self, altura: str | None, visada: str | None) -> None:
        self.altura_da_antena = altura
        self.linha_de_visada = visada


class _DeclaracaoFalsa:
    def __init__(self, altura: str | None, visada: str | None) -> None:
        self.mesa = _MesaFalsa(altura, visada)


# ---------------------------------------------------------------------------
# 1. A ORDEM DE SERVIÇO — a mentira mais cara desta aba
# ---------------------------------------------------------------------------
def test_a_ordem_de_servico_e_da_maquina_dela() -> None:
    """O card traz o imperativo da ordem viva, e NADA do mockup."""
    p = _pacote()
    ordem = _uma_ordem()
    antes = p._ORDENS_NA_TELA
    try:
        p._ORDENS_NA_TELA = (None, ordem, None)
        card = p._html_da_ordem()
    finally:
        p._ORDENS_NA_TELA = antes

    assert ordem.acao in card, (
        f"o card não traz o imperativo da ordem viva. Saiu: {card[:200]!r}")
    assert FRASE_DO_MOCKUP not in card, (
        "a frase cravada no mockup voltou ao card — é uma INSTRUÇÃO para ela "
        "mexer no gabinete, sobre entradas que a máquina dela pode não ter")
    assert "Não medi o ganho nesta máquina." in card, (
        "o `ganho_esperado` sumiu do card. AS TRÊS LINHAS, SEMPRE — inclusive a "
        "que confessa que o ganho não foi medido (`secao_exame._card_da_ordem`)")


def test_o_card_traz_as_duas_frases_da_ordem_no_interrogacao() -> None:
    """O `?` é *O que eu vi aqui* e *Por que importa*, com os rótulos do dono."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ROTULOS_DA_ORDEM

    p = _pacote()
    ordem = _uma_ordem()
    dica = p._dica_da_ordem(ordem)

    for rotulo, linha in zip(ROTULOS_DA_ORDEM[:2], ordem.linhas[:2], strict=True):
        assert f"<b>{rotulo}:</b>" in dica, (
            f"o `?` do card perdeu o rótulo {rotulo!r}, que é de "
            "`exame_da_mesa.ROTULOS_DA_ORDEM`")
        assert linha.texto in dica, f"o `?` perdeu a frase {linha.texto!r}"

    assert ordem.ganho_esperado.texto not in dica, (
        "o ganho está no `?` E na linha `Ganho esperado:` do card — a mesma "
        "frase duas vezes no mesmo cartão é a decisão 9 dela desfeita")


def test_sem_destino_o_card_nao_desenha_um_de_para_de_travessoes() -> None:
    """`destino=''` é o caso das DUAS ordens desta máquina — sem receita."""
    p = _pacote()
    assert 'class="receita"' not in p._card_da_ordem(_uma_ordem(destino="")), (
        "com destino vazio o card desenhou o de→para, e ele sai `— → —`: "
        "ruído com cara de diagnóstico")
    com_destino = p._card_da_ordem(_uma_ordem(destino="Entrada 9"))
    assert 'class="receita"' in com_destino and "Entrada 9" in com_destino, (
        "com destino o card TEM de mostrar para onde mandar")


def test_sem_ordem_a_coluna_diz_a_frase_do_produto() -> None:
    """Zero ordens tem texto próprio, e ele é do dono — nunca um quadro vazio."""
    from hefesto_dualsense4unix.gui.aba_conexoes import html_da_ordem

    p = _pacote()
    antes = p._ORDENS_NA_TELA
    try:
        p._ORDENS_NA_TELA = (None, None)
        assert p._html_da_ordem() == html_da_ordem(None), (
            "sem ordem, a coluna tem de dizer exatamente o que "
            "`gui.aba_conexoes.html_da_ordem(None)` diz")
    finally:
        p._ORDENS_NA_TELA = antes


def test_o_dono_ainda_nao_desenha_a_ordem_da_mesa() -> None:
    """A CATRACA DA SEGUNDA GRAFIA — e ela fica VERMELHA quando o dono curar.

    `gui.aba_conexoes.html_da_ordem` lê `ordem.alvo.onde`, e
    `ordens_da_mesa.Identidade` nunca teve `onde` — tem `vid`, `pid`, `caminho`
    e `ambigua`. A função **jamais correu com uma `Ordem`**: o único chamador
    era `aba_conexoes.pintura:935`, e `pintura(ordem=None)` é o padrão. Ramo
    morto por construção, achado em 03/09/2026 ao ligá-la ao produto.

    Enquanto for assim, `a08_conexoes._card_da_ordem` desenha aqui. No dia em
    que alguém curar o dono — `gui/aba_conexoes.py` é de outro — este teste
    reprova, e quem o ler apaga a segunda grafia e volta a chamar o dono.
    Uma duplicação que sabe a data da própria morte é dívida com prazo; uma que
    não sabe é só dívida.
    """
    p = _pacote()
    assert not p._dono_sabe_desenhar_a_ordem(), (
        "`gui.aba_conexoes.html_da_ordem` já aguenta uma `Ordem` de verdade. "
        "ENTÃO APAGUE `a08_conexoes._card_da_ordem` e chame o dono em "
        "`_html_da_ordem` — a segunda grafia existia só por causa do defeito.")


# ---------------------------------------------------------------------------
# 1b. O EXAME DE ENTRADA — uma vez, e NUNCA na thread que pinta
# ---------------------------------------------------------------------------
def test_o_exame_de_entrada_nao_corre_na_thread_do_tique() -> None:
    """O tique tem 500 ms e `busctl` tem teto de 5 s. Ele TEM de ir para fora.

    A cicatriz é da janela estável e tem endereço:
    BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01 — um `subprocess.run` síncrono
    travou a janela dela e, em D-state, nem o `kill` chegava. Aqui a thread que
    chama `pacote()` é a do GTK do piloto, e a regra é a mesma.

    A RÉGUA NÃO DEPENDE DO ESCALONADOR, que é a armadilha número um desta casa:
    ela troca `_correr_o_exame_completo` por um dublê que ANOTA em qual thread
    foi chamado, e compara com a thread do teste.
    """
    import threading

    p = _pacote()
    onde: list[str] = []
    antes_fn, antes_flag = p._correr_o_exame_completo, p._EXAME_PEDIDO
    try:
        p._correr_o_exame_completo = (  # type: ignore[assignment]
            lambda: onde.append(threading.current_thread().name))
        p._EXAME_PEDIDO = False
        p._pedir_o_exame_de_entrada()
        for t in threading.enumerate():
            if t.name == "hefesto-exame-de-entrada":
                t.join(timeout=5)
    finally:
        p._correr_o_exame_completo = antes_fn  # type: ignore[assignment]
        p._EXAME_PEDIDO = antes_flag

    assert onde, "o exame de entrada não correu de jeito nenhum"
    assert onde[0] != threading.current_thread().name, (
        f"o exame completo correu na thread de quem pediu ({onde[0]!r}) — no "
        "produto essa é a thread que pinta, e ela ficaria parada até o teto do "
        "`busctl`")


def test_o_exame_de_entrada_e_uma_vez_so_mesmo_falhando() -> None:
    """Sem a trava, um exame que falha vira um `busctl` a cada 500 ms."""
    import threading

    p = _pacote()
    vezes: list[int] = []

    def explode() -> None:
        vezes.append(1)
        raise RuntimeError("não consegui examinar as entradas agora")

    antes_fn, antes_flag = p._correr_o_exame_completo, p._EXAME_PEDIDO
    try:
        p._correr_o_exame_completo = explode  # type: ignore[assignment]
        p._EXAME_PEDIDO = False
        for _ in range(5):
            p._pedir_o_exame_de_entrada()
        for t in threading.enumerate():
            if t.name == "hefesto-exame-de-entrada":
                t.join(timeout=5)
    finally:
        p._correr_o_exame_completo = antes_fn  # type: ignore[assignment]
        p._EXAME_PEDIDO = antes_flag

    assert len(vezes) == 1, (
        f"cinco tiques dispararam {len(vezes)} exames. Quem rearma é o botão "
        "**Examinar Portas**, que é gesto dela — nunca a falha")


# ---------------------------------------------------------------------------
# 2. A SALA — a tela dizia que ela não respondeu o que ela respondeu
# ---------------------------------------------------------------------------
def test_a_sala_pinta_o_que_ela_ja_declarou() -> None:
    p = _pacote()
    na_tela = p._sala_na_tela(_DeclaracaoFalsa("acima", "com_gente"))
    assert na_tela == {"sala-altura": "acima", "sala-visada": "com_gente"}, (
        f"o pacote não devolveu as duas respostas dela: {na_tela!r}. Sem elas a "
        "tela diz que ninguém respondeu, e ela clica de novo")


def test_o_none_da_sala_nao_acende_o_nao_sei() -> None:
    """`None` é "nunca respondeu" E "respondeu Não sei" — o produto não separa.

    A regra é do dono: `secao_mesa:672` só chama `set_active_id` quando o valor
    gravado não é `None`. Acender o "Não sei" aqui poria na boca dela uma
    resposta que ela pode não ter dado.
    """
    p = _pacote()
    na_tela = p._sala_na_tela(_DeclaracaoFalsa(None, None))
    assert na_tela == {"sala-altura": "", "sala-visada": ""}, (
        f"o `None` do disco virou {na_tela!r} — e o vazio é o único valor que "
        "não acende nenhum dos três botões")
    assert p._ID_NAO_SEI not in na_tela.values(), (
        "o pacote emitiu o id do 'Não sei'. Ele existe só para tirar o terceiro "
        "botão do modo booleano do `escrever()`; emiti-lo é afirmar por ela")


def test_os_tres_botoes_da_sala_tem_o_seu_proprio_quando() -> None:
    """Sem `data-hef-quando` distinto, o alvo `classe` acenderia os três juntos."""
    html = BANCADA.read_text(encoding="utf-8")
    for gesto, ids in (("sala-altura", {"acima", "abaixo"}),
                       ("sala-visada", {"com_gente", "livre"})):
        bloco = re.findall(
            rf'data-gesto="{gesto}"[^>]*data-hef-quando="([a-z_]*)"', html)
        assert len(bloco) == 3, (
            f"o desenho tem {len(bloco)} botão(ões) de `{gesto}` com "
            "`data-hef-quando`; são três")
        assert len(set(bloco)) == 3, (
            f"dois botões de `{gesto}` dizem ser o mesmo valor: {bloco!r}")
        assert ids <= set(bloco), (
            f"os ids do produto {sorted(ids)} sumiram do `{gesto}`: {bloco!r}")
        assert "" not in bloco, (
            f"um botão de `{gesto}` ficou com `data-hef-quando` VAZIO, e vazio "
            "é o modo booleano do `escrever()` — ele acenderia sozinho")


# ---------------------------------------------------------------------------
# 3. A TIRA DO CHECK-UP — o que sobra tem de ser o mais barato de perder
# ---------------------------------------------------------------------------
class _ItemFalso:
    def __init__(self, chave: str, ordem: object | None) -> None:
        self.chave = chave
        self.estado = ("atencao" if ordem is not None  # (noqa-acento) chave de estado
                       else "certo")
        self.rotulo = chave
        self.porque = chave
        self.ordem = ordem


def test_as_ordens_vem_antes_das_conferencias() -> None:
    """A regra é do produto — `secao_exame._desenhar_o_que_fazer`.

    O desenho tem CINCO blocos de exame e o exame completo desta bancada
    devolve SETE itens. Sem a ordenação, as duas que sobram são exatamente as
    duas que ACUSAM, e a tira fica com cinco CERTO.
    """
    p = _pacote()
    ordem = _uma_ordem()
    conferencias = [_ItemFalso(f"conf{i}", None) for i in range(5)]
    achados = [_ItemFalso("com_ordem_a", ordem), _ItemFalso("com_ordem_b", ordem)]

    antes_conf, antes_extras, antes_disp = (
        p._conferencias, p._EXTRAS, dict(p._DISPENSADAS))
    try:
        p._conferencias = lambda: list(conferencias)  # type: ignore[assignment]
        p._EXTRAS = tuple(achados)
        p._DISPENSADAS = {}
        tira = p._itens_da_tela()
    finally:
        p._conferencias = antes_conf  # type: ignore[assignment]
        p._EXTRAS, p._DISPENSADAS = antes_extras, antes_disp

    assert len(tira) == 7, f"a tira perdeu itens: {[i.chave for i in tira]}"
    cinco = [i.chave for i in tira[:5]]
    assert {"com_ordem_a", "com_ordem_b"} <= set(cinco), (
        f"as duas linhas que ACUSAM caíram fora dos cinco blocos: {cinco}. "
        "A tela mostraria cinco CERTO com dois achados abertos escondidos")
    assert [i.chave for i in tira[2:]] == [c.chave for c in conferencias], (
        "a ordem de chegada das conferências mudou — `sorted` é estável e o "
        "que vem depois das ordens é a ordem dos cinco rótulos da janela")


# ---------------------------------------------------------------------------
# 4. OS DOIS NÚMEROS QUE A LINHA FECHADA MOSTRAVA DO DESENHO
# ---------------------------------------------------------------------------
def test_a_bateria_sem_leitura_vira_o_travessao_do_produto() -> None:
    from hefesto_dualsense4unix.gui.aba_conexoes import TRACO

    p = _pacote()
    assert p._texto_da_bateria(64) == "64%"
    assert p._texto_da_bateria(None) == TRACO, (
        "sem leitura, a bateria tem de mostrar o travessão do produto — um "
        "número herdado é a tela afirmando o que ninguém leu")
    assert p._texto_da_bateria("nao_e_numero") == TRACO


def test_a_contagem_da_gestao_e_do_dono_com_o_separador_do_desenho() -> None:
    """A frase inteira vem de `gui.aba_conexoes.texto_da_contagem`."""
    from hefesto_dualsense4unix.gui import aba_conexoes as tela

    p = _pacote()
    estado = {"controllers": [
        {"connected": True, "uniq": "aa:bb:cc:00:00:01", "transport": "usb",
         "player": 1, "battery_pct": 88},
        {"connected": True, "uniq": "aa:bb:cc:00:00:02", "transport": "bt",
         "player": 2, "battery_pct": None},
        {"connected": True, "uniq": "aa:bb:cc:00:00:03", "transport": "bt",
         "player": 3, "battery_pct": 10}]}
    frase = tela.texto_da_contagem(tela.controles_do_estado(estado))
    assert frase == "3 controles • 1 no cabo • 2 no rádio", (
        f"o dono mudou a frase da contagem: {frase!r}")

    saiu = p.html_da_conta(frase)
    assert saiu.count('<span class="pt">•</span>') == 2, (
        f"o separador do desenho não entrou: {saiu!r}")
    assert " • " not in saiu, "sobrou um `•` cru, que a folha dela não apaga"


def _ctx():  # type: ignore[no-untyped-def]
    """Uma mesa de dois, um sem leitura de bateria — o caso que morde.

    A FAIXA SINTÉTICA DA CASA nos `uniq`: há dois portões de anonimato nesta
    árvore, e um MAC de bancada num arquivo versionado reprova nos dois.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": None},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_liga_os_cinco_enderecos() -> None:
    """A METADE QUE MORDE, e ela é a ligação — não a peça.

    MEDIDO EM 03/09/2026, arrancando as quatro curas de uma vez: com
    `"bateria": c.get("battery_pct")` de volta no `pacote()`, os outros quatro
    testes deste arquivo reprovaram e **o da bateria continuou verde**, porque
    ele chamava `_texto_da_bateria` DIRETO. Um teste que prova a peça e não o
    fio dá verde sobre um fio solto — é o defeito de régua que esta casa mais
    paga, e ele foi cometido de novo aqui.
    """
    from hefesto_dualsense4unix.gui.aba_conexoes import TRACO

    p = _pacote()
    saiu = p.pacote(_ctx())

    for endereco in ("ordem", "conta-gestao"):
        assert endereco in saiu, (
            f"o `pacote()` não emite `{endereco}` — o desenho tem o endereço e "
            "ninguém escreve nele")
    assert saiu["conta-gestao"].startswith("2 controles"), (
        f"a contagem da seção não conta a mesa deste contexto: "
        f"{saiu['conta-gestao']!r}")

    baterias = [c.get("bateria") for c in saiu["colunas"].values()]
    assert baterias == ["100%", TRACO], (
        f"o `pacote()` emitiu {baterias!r}. A bateria é TEXTO — um inteiro num "
        "endereço de texto escreve `100` onde o desenho promete `100%`, e "
        "`null` onde ele promete o travessão")


# ---------------------------------------------------------------------------
# 5. O DESENHO TEM ONDE ESCREVER — sem endereço, o pacote pinta zero, calado
# ---------------------------------------------------------------------------
def test_o_desenho_tem_endereco_para_os_cinco() -> None:
    """O `bateria` VALE 4 DESDE 07/09/2026, e o número não é digitado.

    Ele era `2` — um por controle CONECTADO da `monta.MESA`, que traz dois
    ligados e dois vazios. A conta estava certa para o mundo em que o cartão
    vazio nascia sem um `data-campo` por dentro, e esse mundo era o defeito:
    com os quatro DualSense dela na mesa, o daemon publicava quatro, a carga
    chegava com os quatro e a tela mostrava DOIS, porque o passo 2 do piloto
    procura `data-campo` DENTRO de `[data-controle="pN"]` e nos dois lugares
    vazios não havia nenhum.

    AGORA SÃO OS QUATRO LUGARES, e a régua LÊ o tamanho da mesa em vez de o
    cravar: no dia em que a bancada mudar de tamanho, o número que ela cobra
    muda junto. Um literal aqui é a mesma dívida que o `2` era — uma régua que
    mede o mundo do dia em que foi escrita.
    """
    from monta import MESA

    html = BANCADA.read_text(encoding="utf-8")
    esperado = {"ordem": 1, "conta-gestao": 1, "sala-altura": 3,
                "sala-visada": 3, "bateria": len(MESA)}
    for campo, quantos in esperado.items():
        achados = html.count(f'data-campo="{campo}"')
        assert achados == quantos, (
            f"`data-campo=\"{campo}\"` aparece {achados}x na bancada e o pacote "
            f"o emite esperando {quantos}. Endereço que não existe faz o "
            "`achar()` do piloto escrever ZERO, calado — foi assim que `via`, "
            "`bateria`, `ponte` e `fragil` somaram à cobertura sem chegar à tela")

    for campo in ("ordem", "conta-gestao"):
        assert re.search(rf'data-campo="{campo}" data-hef-alvo="html"', html), (
            f"`{campo}` troca um bloco INTEIRO e precisa do alvo `html`; sem "
            "ele o piloto escreveria a marcação como texto na tela")
