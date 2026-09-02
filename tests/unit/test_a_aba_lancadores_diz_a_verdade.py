#!/usr/bin/env python3
"""A RÉGUA DA ABA LANÇADORES: o que ela AFIRMA tem de vir de uma medição.

POR QUE ELA EXISTE, e é a razão de a aba ter sido reaberta: até 02/09/2026 a
página `07-lancadores.html` era desenho inteiro — zero gestos, zero campos
escritos — e afirmava quatro números que o produto contradiz. Medido na máquina
dela, com `censo_do_wrapper(anotar=False)` e `prontuario_dos_jogos`:

    o HTML afirmava                  o produto responde
    ------------------------------   ------------------------------------------
    Steam · 412 jogos                23 jogos INSTALADOS
    ◆ 3 jogos já sabem por onde      0 pontes confirmadas
    5 encontrados · 1 impedimento    1 lançador medível
    Heroic · 28 jogos · NÃO CHEGAM   nenhuma função do produto olha o Heroic

O QUE ESTA RÉGUA COBRA, e cada item é uma forma de recaída:

1. **Todo endereço da página tem quem o pinte, e todo valor tem onde cair.** Um
   valor emitido para um endereço que não existe é pintura perdida:
   `querySelector` devolve `null`, a pintura conta zero, e zero passa por
   "nada mudou".
2. **Nenhum cartão sem fonte AFIRMA.** `CHEGAM` e `NÃO CHEGAM` sobre um
   lançador que ninguém mede é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor verde.
3. **O selo segue os REPARÁVEIS, não os faltantes.** Um jogo com a lista de
   IGNORE estendida à mão está sem o wrapper e o produto NÃO o toca — contá-lo
   como "não chega" acenderia um `Consertar` que não conserta aquele jogo.
4. **A pintura NÃO ESCREVE EM DISCO.** É a mordida mais importante daqui: o
   `censo_do_wrapper` com `anotar=True` grava o `wrapper-visto.json`, a memória
   que separa "perdeu" de "nunca teve". Uma pintura que anotasse marcaria todo
   jogo novo como "já visto" antes de ela ver o aviso uma vez.
5. **Os gestos agem no ARQUIVO, e recusam dizendo quando o clique não diz qual
   jogo.** Um `tirar-daqui` sem appid tiraria um jogo escolhido por acaso.

A MORDIDA (a que o relatório desta frente cola): troque `anotar=False` por
`anotar=True` no `_ler_do_disco` e o item 4 reprova; troque `censo.reparaveis`
por `censo.faltantes` e o item 3 reprova; apague um `data-campo` do
`um_cartao` e o item 1 reprova nomeando o endereço.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"

#: OS ENDEREÇOS QUE O CABEÇALHO PINTA, e não o pacote da aba. Eles são das DEZ
#: páginas (`pacotes.topo()`), e cobrá-los deste pacote faria a régua exigir que
#: cada aba reescrevesse o que já tem dono — o defeito que o comentário do
#: `a01_jogar.py:67` nomeia.
DO_CABECALHO = {"conta", "conta-b", "perfil"}

CAMPO = re.compile(r'data-campo="([^"]+)"')
GESTO = re.compile(r'data-gesto="([^"]+)"')


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"}, mesa=[],
                            conectados=[], estados={})


def _bancada() -> str:
    """A página da BANCADA — o desenho de HOJE, não o congelado.

    Apontar para o publicado daria **verde sobre a página congelada**, que é a
    armadilha mais cara do `COMO-OLHAR-A-TELA.md` (*"régua que pergunta no
    lugar errado produz não-achado convincente"*). Enquanto ela não publicar a
    07, o publicado é o desenho de 31/08, sem um endereço sequer.
    """
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    return caminho.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. o casamento: nada emitido cai no chão, nada da página fica sem dono
# --------------------------------------------------------------------------
def test_todo_endereco_da_pagina_tem_quem_o_pinte(a07, ctx):
    """Zero vazios e zero órfãos — nos DOIS sentidos.

    Um endereço sem dono fica com o valor do desenho para sempre (e a régua do
    mockup da casa o conta como MOCKUP); um valor sem endereço é escrito no
    nada. As duas falhas são invisíveis na tela, que é por que estão aqui.
    """
    da_pagina = set(CAMPO.findall(_bancada())) - DO_CABECALHO
    emite = {k for k in a07.pacote(ctx) if k not in ("sem_dono", "cobertura")}
    assert da_pagina, "a página não tem um endereço sequer — a régua ficou cega"
    assert da_pagina - emite == set(), (
        f"a página tem estes endereços e o pacote não os manda: "
        f"{sorted(da_pagina - emite)}. Eles ficam com o valor do desenho.")
    assert emite - da_pagina == set(), (
        f"o pacote manda estes valores e a página não tem onde pô-los: "
        f"{sorted(emite - da_pagina)}. `querySelector` devolve `null` e a "
        f"pintura conta zero — sem uma linha de erro.")


def test_todo_gesto_do_html_tem_dono_ou_esta_declarado_sem_dono(a07):
    """Um botão com endereço e sem quem o atenda some no clique.

    O contrário também é cobrado: um gesto registrado que a página não tem
    nunca é clicado, e passa por qualquer régua que só olhe o registro.
    """
    import pacotes

    no_html = set(GESTO.findall(_bancada()))
    com_dono = {n for (p, n) in pacotes.GESTOS if p == PAGINA}
    # O HTML estático nasce no estado "ainda não li o disco": só os botões
    # daquele estado aparecem nele. Os demais entram pela pintura de `-acoes`.
    assert no_html <= com_dono, (
        f"a página tem gestos que ninguém atende: {sorted(no_html - com_dono)}")
    assert com_dono - no_html <= {"consertar", "ver-o-que-impede",
                                  "tirar-daqui", "voltar-a-usar"}, (
        f"estes gestos têm dono e não aparecem em estado nenhum da página: "
        f"{sorted(com_dono - no_html)}")


def test_os_botoes_que_a_pintura_traz_existem_no_html_pintado(a07, ctx, desenho):
    """Os quatro que faltam no HTML estático chegam pela fileira `-acoes`.

    Sem esta régua, `Consertar` poderia ter dono, ter prova unitária e **nunca
    aparecer na tela** — porque a fileira de botões do cartão da Steam é
    pintada, e um erro ali é mudo.
    """
    lida = desenho.Leitura(
        com_wrapper=("1",),
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),),
        instalados=3, frase="alguma frase")
    html = desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-acoes"]
    for nome in ("consertar", "ver-o-que-impede"):
        assert f'data-gesto="{nome}"' in html, (
            f"o cartão da Steam com jogo faltando não traz o botão {nome!r}")
    ok = desenho.Leitura(com_wrapper=("1",), instalados=1)
    html_ok = desenho.Quadro(
        lancadores=desenho.cartoes(ok)).valores()["steam-acoes"]
    assert 'data-gesto="consertar"' not in html_ok, (
        "o `Consertar` continua aceso numa biblioteca em ordem — um clique que "
        "não conserta nada é o botão que finge")


# --------------------------------------------------------------------------
# 2. o que a tela AFIRMA
# --------------------------------------------------------------------------
def test_nenhum_lancador_sem_fonte_afirma_que_os_controles_chegam(desenho):
    """`CHEGAM`/`NÃO CHEGAM` só para quem o produto MEDE.

    A prova de que os cinco não são medidos, refeita a cada execução: nenhum
    módulo de `src/` os nomeia fora de comentário.
    """
    for chave, _nome in desenho.SEM_FONTE:
        cartao = next(c for c in desenho.cartoes(None) if c.chave == chave)
        assert cartao.selo == "nao_sei", (
            f"o cartão {chave!r} afirma {desenho.SELOS[cartao.selo]!r} e o "
            f"produto não tem uma função que o olhe.")


def test_os_cinco_lancadores_sem_fonte_continuam_sem_fonte():
    """A MORDIDA DO OUTRO LADO: se alguém escrever o censo do Heroic, aqui acusa.

    ELA LÊ CÓDIGO, e não texto. A primeira versão desta régua descartava só o
    que vinha depois de um `#` e reprovou com QUATRO achados — os quatro em
    docstring (`profiles/schema.py:1336`, `daemon/lifecycle.py:2271` e `:4169`,
    `daemon/subsystems/game_signal.py:97`), que é exatamente a prosa que
    documenta *"nós ainda não olhamos isto"*. Contar prosa como código é a
    mesma forma de erro que produziu o "77% da interface" de 01/09: **presença
    de string não é funcionamento.**

    O `tokenize` resolve porque descarta comentário E literal de texto de uma
    vez — sobra identificador, que é o que denuncia código de verdade.
    """
    import io
    import tokenize

    nomes = re.compile(r"heroic|lutris|retroarch|dolphin|mgba", re.IGNORECASE)
    #: Estes NOMEIAM os cinco de propósito: um é o desenho dos cartões, os
    #: outros são a aba que os mostra. Isentá-los é o que impede a régua de
    #: acusar a própria cura.
    meus = {"aba07.py", "aba10.py", "desenho_dos_lancadores.py",
            "a07_lancadores.py"}
    fora: list[str] = []
    for arq in (RAIZ / "src").rglob("*.py"):
        if arq.name in meus:
            continue
        texto = arq.read_text(encoding="utf-8")
        if not nomes.search(texto):
            continue  # nem em prosa — não há o que examinar
        try:
            fichas = list(tokenize.generate_tokens(io.StringIO(texto).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            continue
        for f in fichas:
            if f.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            if nomes.search(f.string):
                fora.append(f"{arq.relative_to(RAIZ)}:{f.start[0]} → {f.string}")
    assert fora == [], (
        f"o produto passou a olhar um destes lançadores EM CÓDIGO: {fora}. Ele "
        f"SAI do `desenho_dos_lancadores.SEM_FONTE` e ganha cartão com fonte — "
        f"o `NÃO SEI` dele virou mentira no minuto em que esta linha nasceu.")


def test_nenhum_cartao_promete_um_numero_de_controles(desenho):
    """A recaída da régua velha do gerador, cobrada também aqui.

    Ela existia porque a aba prometia "Os 4 controles chegam" com dois na mesa.
    A resposta desta aba é POR LANÇADOR — nenhum dos cinco impedimentos de
    `prontuario_dos_jogos` recebe controle, MAC, device ou transporte.
    """
    grade = _bancada().split('<div class="lancadores">', 1)[-1].split("</div>\n\n")[0]
    assert 'data-lancador="steam"' in grade, (
        "a régua não achou a grade de cartões — seletor que casa ZERO é erro, "
        "não silêncio")
    tudo = desenho.cartoes_html(desenho.cartoes(None)) + grade
    assert not re.findall(r"[Oo]s \d+ controles chegam", tudo), (
        "um cartão voltou a prometer para um NÚMERO de controles")


def test_o_selo_segue_os_reparaveis_e_nao_os_faltantes(desenho):
    """Um jogo INTOCÁVEL não acende o `Consertar`.

    `apply_wrapper_vdf_text` pula a linha com a lista de IGNORE estendida à mão
    por construção: remover só o trecho do Hefesto deixaria um fragmento-comando
    e o jogo nunca mais abriria. Um selo `NÃO CHEGAM` ali ofereceria um reparo
    que o produto se recusa a fazer.
    """
    so_intocavel = desenho.Leitura(
        com_wrapper=("1", "2"),
        intocaveis=(("9", "Jogo intocável", "linha editada à mão — não vou tocar"),),
        instalados=3)
    cartao = desenho.cartao_da_steam(so_intocavel)
    assert cartao.selo == "ok", (
        "o cartão diz NÃO CHEGAM por causa de um jogo que o produto não toca")
    assert 'data-gesto="consertar"' not in desenho.acoes_html(cartao), (
        "o `Consertar` está aceso e não há nada que ele possa consertar")
    assert "intocável" in cartao.carimbo, (
        "o jogo intocável sumiu da tela — ele fica sem o atalho para sempre e "
        "ninguém saberia")


def test_o_nome_do_jogo_e_escapado(desenho):
    """O rótulo vem do `appmanifest` DELA — é conteúdo de terceiro."""
    lida = desenho.Leitura(
        reparaveis=(("7", '<b>&"joguinho"', "nunca recebeu o atalho"),),
        instalados=1)
    html = desenho.lista_de_jogos(lida)
    assert "<b>&" not in html and "&lt;b&gt;" in html, (
        "um nome de jogo com marcação quebraria o cartão")


# --------------------------------------------------------------------------
# 3. a pintura não toca o disco, e não bloqueia
# --------------------------------------------------------------------------
def test_a_pintura_nunca_grava_o_registro_de_wrapper_visto(a07, monkeypatch):
    """A MORDIDA PRINCIPAL: `anotar=False`, e ele não é zelo.

    Com `anotar=True`, a primeira pintura marcaria TODO jogo com wrapper como
    "já visto" — e a distinção regressão/novo, que é o que nomeia o defeito do
    Pragmata, nasceria morta. Troque para `True` no `_ler_do_disco` e este
    teste reprova.
    """
    from types import SimpleNamespace

    vistos: list[bool] = []
    vazio = SimpleNamespace(com_wrapper=[], reparaveis=[], intocaveis=[],
                            recusados=[], erros=[])

    def _espiao(*a, **kw):
        vistos.append(bool(kw.get("anotar", True)))
        return vazio

    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    monkeypatch.setattr(sw, "censo_do_wrapper", _espiao)
    monkeypatch.setattr(sw, "frase_do_aviso", lambda c: "")
    a07._ler_do_disco()
    assert vistos == [False], (
        f"a leitura da tela pediu `anotar={vistos}`. Com `True` ela GRAVA o "
        f"`wrapper-visto.json` a cada tique, e todo jogo novo vira 'já visto' "
        f"antes de ela ver o aviso uma única vez.")


def test_o_tique_nao_bloqueia_no_disco(a07, ctx, monkeypatch):
    """A pintura devolve o que tem — nunca espera o disco.

    Medido em 02/09/2026: `censo_do_wrapper` custa 26 ms e `levantar_censo`
    13,4 s, contra um tique de 500 ms. Se a pintura chamasse o disco, a janela
    inteira pararia — e o `--passear` mediria 26 ms por volta em vez de 0,3.
    """
    def _nunca(*a, **kw):
        raise AssertionError("a pintura leu o disco na thread da janela")

    monkeypatch.setattr(a07, "_ler_do_disco", _nunca)
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "_dado", None, raising=False)
    pacote = a07.pacote(ctx)
    assert pacote["steam-jogos"] == a07.desenho.AINDA_LENDO, (
        "sem leitura o cartão tem de dizer que ainda está lendo — um número "
        "que não foi lido é um número inventado")


# --------------------------------------------------------------------------
# 4. os gestos agem no arquivo, e recusam dizendo
# --------------------------------------------------------------------------
def _gesto(nome):
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, nome)
    assert fn is not None, f"{PAGINA}:{nome} não tem dono"
    return fn


@pytest.mark.parametrize("nome", ["tirar-daqui", "voltar-a-usar"])
def test_o_gesto_sem_appid_recusa_e_nao_escreve(nome, ctx, monkeypatch):
    """Um clique sem `data-v` tiraria um jogo escolhido por acaso."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    def _nunca(*a, **kw):
        raise AssertionError("escreveu no arquivo com o clique recusado")

    monkeypatch.setattr(slo, "marcar_jogo_sem_wrapper", _nunca)
    monkeypatch.setattr(slo, "desmarcar_jogo_sem_wrapper", _nunca)
    with pytest.raises(ValueError):
        _gesto(nome)(ctx, {"controle": "p1", "texto": "x"}, None)


def test_tirar_e_voltar_a_usar_escrevem_no_arquivo_de_verdade(ctx, a07):
    """O par completo, contra o `jogos_sem_wrapper.txt` do lar de mentira.

    O `conftest.py` desta casa desvia `HOME` e os quatro `XDG_*`, então este
    teste escreve num arquivo temporário — nunca no dela. É a prova mais forte
    que estes botões podem ter: não "a função foi chamada", mas **o arquivo
    mudou**.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    caminho = slo.sem_wrapper_path()
    assert "1070560" not in slo.ler_jogos_sem_wrapper(), "o lar de mentira sujo"

    _gesto("tirar-daqui")(ctx, {"v": "1070560"}, None)
    assert "1070560" in slo.ler_jogos_sem_wrapper(), (
        f"o gesto disse que aplicou e {caminho} não tem o appid")

    _gesto("voltar-a-usar")(ctx, {"v": "1070560"}, None)
    assert "1070560" not in slo.ler_jogos_sem_wrapper(), (
        "o jogo ficou preso fora da lista — um gesto que só vai numa direção "
        "deixa a pessoa presa no estado em que clicou")


def test_consertar_recusa_dizendo_quando_a_steam_esta_aberta(ctx, monkeypatch):
    """A recusa vai para a TELA, e com a frase da sentinela.

    `RuntimeError` é o contrato desta casa para "o produto recusou" — e a
    frase precisa nomear o jogo e dizer o que vai acontecer, porque
    *"1 jogo com problema"* é o texto que deixou o Pragmata quebrado a noite
    inteira.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    from types import SimpleNamespace

    censo = SimpleNamespace(regressoes=[], novos=[], intocaveis=[],
                            jogo_aberto=False, steam_aberta=True)
    monkeypatch.setattr(
        sw, "reparar_ou_adiar",
        lambda *a, **kw: (sw.REPARO_ADIADO_STEAM, censo, None))
    monkeypatch.setattr(sw, "frase_do_aviso",
                        lambda c: "Preciso da Steam FECHADA para repor.")
    with pytest.raises(RuntimeError, match="FECHADA"):
        _gesto("consertar")(ctx, {"v": "steam"}, None)


def test_detectar_recusa_dizendo_quando_nao_ha_jogo(ctx, monkeypatch):
    """Sem jogo aberto o botão RECUSA — não inventa um jogo nem responde calado."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(slo, "steam_game_running_appid", lambda: None)
    with pytest.raises(RuntimeError, match="jogo"):
        _gesto("detectar")(ctx, {}, None)


def test_esta_regua_nao_alcanca_a_biblioteca_dela():
    """A pergunta que custou dez minutos em 02/09, respondida por medição.

    Durante a MORDIDA (com `anotar=True` de propósito) o canário do `conftest`
    avisou que o `~/.local/state/.../wrapper-visto.json` **dela** tinha mudado,
    no minuto exato da execução. A conclusão fácil era "fui eu". Medido, não
    fui: os três caminhos que esta aba toca apontam para o lar de mentira, e
    `discover_vdfs()` devolve LISTA VAZIA — não há biblioteca da Steam a ler.

    Fica como régua porque a dúvida vai voltar: quem mexer nesta aba precisa
    saber, sem investigar de novo, que ela não alcança o disco dela.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    real = str(pathlib.Path.home())
    for caminho in (sw.caminho_do_registro(), slo.sem_wrapper_path()):
        assert not str(caminho).startswith(real + "/.local"), (
            f"a régua escreveria em {caminho}, que é o estado DELA")
    assert slo.discover_vdfs() == [], (
        "a régua enxerga um `localconfig.vdf` de verdade — o isolamento do "
        "`conftest` caiu, e um teste desta aba passaria a ler a biblioteca dela")


def test_o_piso_de_gestos_da_aba_e_seis(a07):
    """Ele SÓ SOBE. Uma queda não aparece na tela: o clique não faz nada."""
    import pacotes

    quantos = sum(1 for (p, _) in pacotes.GESTOS if p == PAGINA)
    assert quantos >= a07.PISO_DA_ABA == 6, (
        f"{PAGINA} tem {quantos} gestos com dono e o piso é {a07.PISO_DA_ABA}")
