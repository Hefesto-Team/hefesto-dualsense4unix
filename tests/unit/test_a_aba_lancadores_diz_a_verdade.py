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

#: OS ENDEREÇOS QUE O TOPO PINTA, e não o pacote da aba. Eles são das DEZ
#: páginas, e cobrá-los deste pacote faria a régua exigir que cada aba
#: reescrevesse o que já tem dono — o defeito que o comentário do
#: `a01_jogar.py:67` nomeia.
#:
#: A LISTA SAI DO DONO, e não se digita — 03/09/2026. Ela era
#: `{"conta", "conta-b", "perfil"}` à mão, e no dia em que o `topo()` ganhou os
#: dois campos do RODAPÉ (a dica do "Salvar Perfil" e a do "Exportar", que
#: passaram a dizer o nome do perfil ativo em vez do exemplo congelado) esta
#: régua reprovou a aba Lançadores por um endereço que não é dela. Ler o dono é
#: o que faz o próximo campo compartilhado entrar sozinho.


def _do_topo() -> set[str]:
    """Os endereços que `pacotes.topo()` emite, perguntados a ele."""
    import pacotes

    class _Vazio:
        """Um `Contexto` sem nada — o `topo()` só precisa das duas chaves."""

        def __init__(self) -> None:
            self.state: dict = {}
            self.mesa: list = []

    return set(pacotes.topo(_Vazio()))

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
    da_pagina = set(CAMPO.findall(_bancada())) - _do_topo()
    emite = {k for k in a07.pacote(ctx)
             if k not in ("sem_dono", "cobertura", "blocos")}
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
    # `copiar-a-linha` ENTROU EM 04/09/2026 e é o caso mais estrito da lista: os
    # outros aparecem no cartão de quem tem jogo faltando, e este só no estado
    # em que há jogo com a LINHA INTOCÁVEL (decisão `07[01]` do PO — *"os dois,
    # só quando faz falta"*). O HTML estático nasce em `cartoes(None)`, que não
    # tem nem leitura de disco nem linha, então ele não pode aparecer ali.
    # Quem prova que ele CHEGA à tela é
    # `test_a_aba_07_lancadores_fecha_as_linhas.py`, sobre a fileira pintada.
    # OS TRÊS DO STEAM INPUT entraram em 06/09/2026 (decisão dela,
    # `D-0609-STEAM-DIVIDIDO`) e caem na MESMA categoria do `copiar-a-linha`:
    # eles só nascem no cartão de quem já teve a biblioteca LIDA
    # (`a07_lancadores.acoes_do_steam_input`), e o HTML estático nasce em
    # `cartoes(None)`, que não leu disco nenhum. Quem prova que chegam à tela é
    # `test_a_aba_07_lancadores_fecha_as_linhas.py`, sobre a fileira pintada.
    assert com_dono - no_html <= {"consertar", "ver-o-que-impede",
                                  "tirar-daqui", "voltar-a-usar",
                                  "voltar-a-perguntar", "nao-perguntar",
                                  "consertar-fechando-a-steam",
                                  "copiar-a-linha",
                                  "desligar-steam-input",
                                  "este-jogo-nao-funciona",
                                  "deixar-tudo-pronto",
                                  # O «Tirar daqui» ENTROU EM 08/09/2026 e cai
                                  # na mesma categoria: ele só nasce no cartão
                                  # que ELA declarou, e a página estática nasce
                                  # de `cartoes(None)` — sem declaração nenhuma.
                                  # O `adicionar-lancador` NÃO está aqui de
                                  # propósito: o botão global mora no HTML
                                  # estático, e se ele sumir esta régua acusa.
                                  "esquecer-lancador"}, (
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

    E OS TRÊS ESTADOS ENTRAM, desde 02/09 à tarde. O produto passou a PROCURAR
    os cinco (sem ler dentro deles), e a régua tinha de acompanhar: um cartão
    achado, um não achado e um ainda-não-procurado são desenhos diferentes, e
    NENHUM dos três pode afirmar que os controles chegam. Cobrar só o terceiro
    deixaria os outros dois livres para acender `CHEGAM` sem ninguém ver.
    """
    for item in desenho.SEM_FONTE:
        for onde in (None, "", f"{item.chave}.desktop"):
            cartao = desenho.cartao_sem_censo(item, onde)
            assert cartao.selo in ("nao_sei", "off"), (
                f"o cartão {item.chave!r} com onde={onde!r} afirma "
                f"{desenho.SELOS[cartao.selo]!r} e o produto não lê a "
                f"biblioteca dele.")
        # E o `cartoes(None)` — a primeira meia volta — continua no `nao_sei`
        # dos três, porque ali o produto ainda não procurou nada.
        nascendo = next(c for c in desenho.cartoes(None) if c.chave == item.chave)
        assert nascendo.selo == "nao_sei" and not nascendo.presente, (
            f"o cartão {item.chave!r} afirma algo antes de a leitura voltar")


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
    # O QUE SE COBRA É A PROPRIEDADE, e não a contagem de chamadas: a `_Vigia`
    # relê o disco numa THREAD (é o contrato dela — a pintura nunca bloqueia), e
    # essa thread pode cair dentro da janela do espião. Cobrar `== [False]`
    # fazia a régua reprovar por uma chamada A MAIS, que é o certo acontecendo —
    # e uma régua que reprova o certo é desligada na primeira semana. Medido em
    # 02/09/2026: `[False, False]`.
    assert vistos, "ninguém chamou o censo — a régua mediria o vazio"
    assert set(vistos) == {False}, (
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


@pytest.mark.parametrize("nome", ["tirar-daqui", "voltar-a-usar",
                                  "voltar-a-perguntar"])
def test_o_gesto_sem_appid_recusa_e_nao_escreve(nome, ctx, monkeypatch):
    """Um clique sem `data-v` tiraria um jogo escolhido por acaso."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    def _nunca(*a, **kw):
        raise AssertionError("escreveu no arquivo com o clique recusado")

    monkeypatch.setattr(slo, "marcar_jogo_sem_wrapper", _nunca)
    monkeypatch.setattr(slo, "desmarcar_jogo_sem_wrapper", _nunca)
    monkeypatch.setattr(lwd, "remove_dismissed_appid", _nunca)
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


def test_o_piso_de_gestos_da_aba_e_catorze(a07):
    """Ele SÓ SOBE. Uma queda não aparece na tela: o clique não faz nada.

    SUBIU DE SEIS PARA SETE em 02/09/2026, com o "Voltar a perguntar" que a
    decisão dela mandou nascer; DE SETE PARA OITO em 03/09/2026, com o
    "Abrir o lançador" da decisão 17 dela; DE OITO PARA DEZ no mesmo dia, com
    as duas faltas de paridade que a medição das dez abas nomeou — o "Não
    perguntar para este jogo" e o "Posso fechar a Steam por uns 20 segundos?";
    e DE DEZ PARA ONZE em 04/09/2026, com o "Copiar a linha" (decisão `07[01]`
    do PO), que é **o único botão de copiar de toda a interface nova**; e DE
    ONZE PARA CATORZE em 06/09/2026, com os TRÊS do Steam Input que a decisão
    dela (`D-0609-STEAM-DIVIDIDO`) trouxe para esta aba — "Desligar o Steam
    Input", "Este jogo não funciona" e "Deixar tudo pronto"; e DE CATORZE PARA
    DEZESSEIS em 08/09/2026, com o registro do lançador que o Hefesto não
    conhece (pedido dela) — «Adicionar Launcher» e «Tirar daqui».
    """
    import pacotes

    quantos = sum(1 for (p, _) in pacotes.GESTOS if p == PAGINA)
    assert quantos >= a07.PISO_DA_ABA == 16, (
        f"{PAGINA} tem {quantos} gestos com dono e o piso é {a07.PISO_DA_ABA}")


# --------------------------------------------------------------------------
# 6. o que o produto PROCURA — a presença dos cinco sem censo
#
# NASCEU EM 02/09/2026, À TARDE, e a razão é uma distinção que a aba não fazia:
# os cinco cartões diziam `NÃO SEI` por CONSTANTE. Um campo que mostra `NÃO
# SEI` porque o produto mediu e não sabe é honesto; um que mostra `NÃO SEI`
# porque ninguém pintou é o desenho fingindo ser produto — e ler a tela não
# separava os dois.
# --------------------------------------------------------------------------
def _pastas_falsas(monkeypatch, tmp_path, *stems: str):
    """Uma pasta de `.desktop` de mentira, com os atalhos que o teste quiser.

    O `PATH` vai junto e vai VAZIO: sem isso o `shutil.which` cairia no PATH da
    máquina dela, e o `flatpak` de verdade faria o teste passar por acidente —
    a régua daria verde sobre a bancada, não sobre a cura.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    pasta = tmp_path / "applications"
    pasta.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        (pasta / f"{stem}.desktop").write_text(
            "[Desktop Entry]\nName=de mentira\n", encoding="utf-8")
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [pasta])
    monkeypatch.setenv("PATH", str(tmp_path / "sem-binario-nenhum"))
    return pasta


def test_o_produto_procura_os_cinco_pelas_pastas_do_motor(a07, desenho, monkeypatch,
                                                          tmp_path):
    """ACHEI e NÃO ACHEI saem de um `stat`, e não de uma constante.

    A MORDIDA: faça `_onde_estao_os_lancadores` devolver sempre `""` (ou volte
    a montar os cartões com `DIZ_SEM_FONTE` fixo) e este teste reprova nos dois
    lados — o achado deixa de ser achado E o ausente deixa de dizer que
    procurou.
    """
    pasta = _pastas_falsas(monkeypatch, tmp_path, "net.lutris.Lutris")
    onde = dict(a07._onde_estao_os_lancadores())
    # O CAMINHO INTEIRO, e não o `stem`: é o que a frase `DIZ_ACHEI` promete
    # ("dizer ONDE é o que deixa ela conferir a resposta sem acreditar em mim").
    # Com o nome solto, uma máquina com o Heroic nativo E o Heroic por Flatpak
    # não dizia qual dos dois o produto achou — e ela não podia `ls` a resposta.
    assert onde["lutris"] == str(pasta / "net.lutris.Lutris.desktop"), (
        f"o produto não achou o atalho que está em disco, ou jogou fora o "
        f"caminho que torna a resposta conferível: {onde}")
    assert onde["heroic"] == "", (
        "o produto disse ter achado um lançador que não está na pasta")
    # OS SEIS, e a Steam entrou em 02/09 à noite: enquanto a busca percorria
    # `SEM_FONTE` (os CINCO cujo interior o produto não lê), o cartão da Steam
    # era o único cuja PRESENÇA ninguém mediu — e nascia `presente=True`
    # cravado. Ver `test_a_steam_ausente_nao_afirma_que_os_controles_chegam`.
    # A RÉGUA LÊ A LISTA DE FÁBRICA em vez de repetir os nomes: digitá-los aqui
    # faria toda inclusão futura reprovar por estar CERTA, que é o defeito que
    # esta casa nomeou onze vezes em 26/08. O que ela cobra é que a busca
    # percorra TODOS os de fábrica — um lançador pulado volta ao `NÃO SEI` de
    # constante. (A Epic entrou nesta lista em 08/09/2026 e saiu no mesmo dia,
    # por decisão dela; a régua não notou, e é exatamente por LER.)
    assert set(onde) == {x.chave for x in desenho.EMBUTIDOS}, (
        "a busca pulou um lançador — o cartão dele voltaria ao `NÃO SEI` de "
        "constante sem ninguém ver")

    # E O CAMINHO DA PINTURA TAMBÉM, e esta parte NASCEU DA MORDIDA: arrancar a
    # cura no CHAMADOR (`onde_estao = ()` dentro do `_ler_do_disco`) deixava a
    # metade de cima deste teste VERDE, porque ela chama a busca direto. Uma
    # régua que prova a função e não prova quem a chama dá verde sobre uma tela
    # que voltou ao desenho — é *"cura escrita, testada, e nunca ligada"*, que
    # esta casa já nomeou.
    assert dict(a07._ler_do_disco().onde_estao)["lutris"] == str(
        pasta / "net.lutris.Lutris.desktop"), (
        "a busca funciona e a LEITURA não a carrega — a tela volta ao `NÃO "
        "SEI` de constante com este teste verde")


def test_o_atalho_do_kde_nao_e_o_emulador(a07, monkeypatch, tmp_path):
    """`dolphin.desktop` é o gerenciador de arquivos do KDE, não o emulador.

    Casar por PREFIXO acusaria o Dolphin em toda máquina com KDE — um `ACHEI`
    sobre um lançador que não está aqui, que é a mentira que esta aba existe
    para não contar.
    """
    _pastas_falsas(monkeypatch, tmp_path, "dolphin")
    assert dict(a07._onde_estao_os_lancadores())["emuladores"] == "", (
        "o `dolphin.desktop` do KDE passou por emulador")


def test_o_cartao_achado_e_o_nao_achado_dizem_coisas_diferentes(desenho):
    """Os três estados viram três telas — e o `NÃO ACHEI` deixa de ser letra morta.

    `SELOS["off"]` existia desde que o desenho nasceu e NENHUM caminho o
    produzia. Uma palavra que o produto nunca escreve é desenho, não vocabulário.
    """
    item = next(x for x in desenho.SEM_FONTE if x.chave == "heroic")
    nao_procurei = desenho.cartao_sem_censo(item, None)
    nao_achei = desenho.cartao_sem_censo(item, "")
    achei = desenho.cartao_sem_censo(item, "com.heroicgameslauncher.hgl.desktop")

    # ELA LÊ O SELO, E NÃO A PALAVRA — 08/09/2026. Aqui estava digitado
    # `== "NÃO ACHEI"`, e quando ela mandou a palavra virar «NÃO LOCALIZADO»
    # esta linha reprovou a MELHORA em vez do defeito: é a forma exata que as
    # onze réguas de 26/08 tinham. O que a régua tem de cobrar é que o estado
    # «procurei e não achei» produza o selo `off` — a palavra que o `off`
    # mostra é decisão DELA, e muda sem que nada aqui precise mudar.
    assert nao_achei.selo == "off", (
        f"o estado 'procurei e não achei' deixou de produzir o selo `off` — ele "
        f"produz {nao_achei.selo!r}, e a palavra que a tela mostra é "
        f"{desenho.SELOS.get(nao_achei.selo)!r}")
    assert not nao_achei.presente and not nao_procurei.presente
    assert achei.presente, "um lançador achado não conta como encontrado no topo"
    assert len({nao_procurei.diz, nao_achei.diz, achei.diz}) == 3, (
        "dois dos três estados dizem a MESMA frase — a tela voltou a não "
        "separar 'procurei e não achei' de 'ainda não procurei'")
    assert "com.heroicgameslauncher.hgl.desktop" in achei.diz, (
        "o cartão diz que achou e não diz ONDE — sem isso ela não tem como "
        "conferir a resposta sem acreditar em mim")


def test_todo_cartao_tem_botao_nos_tres_estados_e_o_do_ausente_e_outro(desenho):
    """OS SEIS CARTÕES, e o nome desta régua já foi «os cinco».

    **ERA ESSE O DEFEITO.** Enquanto ela olhava `cartao_sem_censo` com UM item,
    o que ela provava era a função dos CINCO — e o sexto cartão, a Steam, tem
    função própria (`cartao_da_steam`). O botão que ela cobra nasceu num lugar
    só, o outro ficou com o velho, e **régua nenhuma da casa olhou para lá**:
    numa máquina sem Steam o cartão dela saía com o selo `NÃO LOCALIZADO` e um
    «Abrir o lançador» que só sabe abrir a Steam que não está lá.

    **E O BURACO FECHAVA POR CIMA**, que é o que fazia dele um beco: a outra
    porta é o botão global, e ele recusa um nome que já tem cartão de fábrica
    mandando usar o botão do cartão — que naquele cartão não existia. A tela
    mandava clicar onde não havia nada.

    ENTÃO A RÉGUA PASSOU A PERCORRER OS CARTÕES QUE O PRODUTO MONTA, e não uma
    função. É a única forma que alcança os dois desenhos, e é a que alcançaria o
    próximo cartão com desenho próprio.

    02/09/2026 — O BOTÃO FICA NOS TRÊS ESTADOS, decisão dela, e ela DESFAZ uma
    mudança que ninguém tinha submetido a ela: o estado `off` nasceu com
    `acoes=()`, pelo argumento (bom) de que abrir um lançador ausente é botão
    que finge. O desenho que ela aprovou tem botão nos cinco, e uma frente não
    tira um botão da tela dela por conta própria.

    08/09/2026 — ELA RESPONDEU, E A RESPOSTA ERA UM TERCEIRO CAMINHO: nem tirar,
    nem manter. *"o Botão Abrir o Lançador deveria ser o Adicionar Launcher"*.
    O botão fica, e passa a fazer a coisa que faz sentido num cartão que não
    achou nada: dizer onde o lançador está.

    A MORDIDA TEM TRÊS METADES, e cada uma nomeia um estado: pôr `acoes=()` em
    qualquer ramo reprova; dar o MESMO rótulo aos dois estados reprova (é o erro
    de quem troca o rótulo no lugar errado e deixa o cartão aceso oferecendo um
    registro que já existe); e **devolver o «Abrir o lançador» ao ramo `off` de
    UM cartão só reprova nomeando aquele cartão** — que é o defeito que esta
    régua não via.
    """
    # OS TRÊS ESTADOS DE TODOS OS CARTÕES, montados pelo produto. `onde_estao`
    # com local vazio é "procurei e não achei"; a chave ausente é "não procurei".
    de_fabrica = [x.chave for x in desenho.EMBUTIDOS]
    achei = desenho.Leitura(
        com_wrapper=("1",), instalados=1,
        onde_estao=tuple((k, f"/usr/bin/{k}") for k in de_fabrica))
    nao_achei = desenho.Leitura(onde_estao=tuple((k, "") for k in de_fabrica))
    estados = {"ainda não procurei": desenho.cartoes(None),
               "procurei e não achei": desenho.cartoes(nao_achei),
               "achei aqui": desenho.cartoes(achei)}

    for estado, cartoes in estados.items():
        assert {c.chave for c in cartoes} == set(de_fabrica), (
            f"o estado {estado!r} não montou os mesmos cartões: "
            f"{sorted(c.chave for c in cartoes)}")
        for cartao in cartoes:
            html = desenho.acoes_html(cartao)
            esperado = (desenho.ADICIONAR_ROTULO if cartao.selo == "off"
                        else "Abrir o lançador")
            assert esperado in html, (
                f"o cartão {cartao.chave!r} em {estado!r} (selo {cartao.selo!r}) "
                f"não oferece «{esperado}» — ela não decidiu isso. A fileira é: "
                f"{html!r}")
            assert 'data-gesto="' in html, (
                f"o botão do cartão {cartao.chave!r} em {estado!r} ficou sem "
                f"endereço: um clique sem `data-gesto` não chega ao Python, e "
                f"quem clica conclui que funcionou")
            if cartao.selo == "off":
                assert "Abrir o lançador" not in html, (
                    f"o cartão {cartao.chave!r} que NÃO localizou oferece «Abrir "
                    f"o lançador» — o produto não sabe abrir o que não achou, e "
                    f"ela pediu o contrário")
            else:
                assert desenho.ADICIONAR_ROTULO not in html, (
                    f"o cartão {cartao.chave!r} em {estado!r} oferece "
                    f"«{desenho.ADICIONAR_ROTULO}» — são dois estados e dois "
                    f"botões, e trocar o rótulo dos dois faz o cartão aceso "
                    f"pedir um registro que já existe")

    # E O DA STEAM, NOMEADO. A régua acima já o cobre por percorrer os cartões;
    # esta linha existe para a MENSAGEM: foi a Steam que ficou de fora, e uma
    # falha genérica não diria isso a quem a ler daqui a um mês.
    steam = next(c for c in estados["procurei e não achei"]
                 if c.chave == desenho.STEAM)
    assert steam.selo == "off", (
        f"a Steam não chegou ao estado NÃO LOCALIZADO nesta leitura "
        f"({steam.selo!r}) — a régua estaria medindo outro estado")
    assert desenho.ADICIONAR_ROTULO in desenho.acoes_html(steam), (
        "o cartão da STEAM que não localizou voltou a ficar sem porta: o "
        "produto não sabe abrir a Steam que não achou, e o botão global recusa "
        "mandando usar o botão DESTE cartão")


def test_localizar_este_lancador_abre_a_tela_de_registro(desenho):
    """O botão do cartão tem de ABRIR a pop-up, e isso é mecânico.

    A `.tela-nova` desta casa aparece por `:target` (`monta.CSS_POPUP`), e **só
    uma âncora muda o fragmento** — um `<button>` com `data-gesto` manda o gesto
    e não abre nada. O botão sairia da tela dela como um clique que grava a
    intenção e não mostra onde digitar.

    ELE É COBRADO NOS SEIS, e não num: foi por ser escrito duas vezes que ele
    faltou na Steam. Hoje ele sai de :func:`desenho.acao_de_localizar`, que é o
    único lugar onde a tag e o destino existem.

    A MORDIDA: tire o `href` de `acao_de_localizar` (ou troque a tag de volta
    para `<button>` em `acao_html`) e esta régua reprova nas duas linhas — a tag
    e o destino — em todos os cartões.
    """
    lida = desenho.Leitura(
        onde_estao=tuple((x.chave, "") for x in desenho.EMBUTIDOS))
    for cartao in desenho.cartoes(lida):
        html = desenho.acoes_html(cartao)
        assert f'<a class="btn" href="#{desenho.TELA_DO_NOVO}"' in html, (
            f"o «{desenho.ADICIONAR_ROTULO}» do cartão {cartao.chave!r} não é "
            f"uma âncora para #{desenho.TELA_DO_NOVO}: a tela de registro abre "
            f"por `:target`, e um `<button>` não muda o fragmento — o clique "
            f"gravaria a intenção e não mostraria onde digitar. A fileira é: "
            f"{html!r}")
        assert f'data-gesto="{desenho.ADICIONAR}"' in html, (
            f"o botão do cartão {cartao.chave!r} não tem endereço")
        assert f'data-v="{cartao.chave}"' in html, (
            f"a âncora do cartão {cartao.chave!r} abre a tela e não diz PARA "
            f"QUAL cartão — a tela nasceria apontando para o alvo anterior")


def test_os_dois_botoes_do_registro_dizem_coisas_diferentes(desenho):
    """A PALAVRA É DELA — 08/09/2026: *"Adicionar novo Lançador? Seria legal um
    sinônimo né?"*.

    TRÊS PEDIDOS NUMA FRASE, e esta régua é dona dos três: **português**,
    **«novo» no que é novo**, e **os dois botões falando palavras diferentes**.
    O rótulo do cartão nasceu em inglês e igual ao do botão global, e os dois
    problemas eram o mesmo problema — dois botões com a mesma frase na mesma
    tela fazem quem lê procurar a diferença que a tela não mostra.

    O SINÔNIMO SE ESCREVE SOZINHO, e é por isso que a régua cobra o selo: o
    cartão que não localizou diz `NÃO LOCALIZADO`, então o botão dele diz
    «Localizar». Selo e botão passam a falar a mesma palavra.

    **POR QUE ESTA RÉGUA PODE DIGITAR as duas frases:** ela é a DONA da decisão
    — o lugar onde a palavra dela fica registrada, para que trocá-la exija
    passar por ela. Toda régua que apenas PRECISA do rótulo lê a constante.

    A MORDIDA: dê o mesmo texto aos dois rótulos e a primeira linha reprova;
    devolva «Launcher» a qualquer um deles e a segunda reprova.
    """
    do_cartao = desenho.ADICIONAR_ROTULO
    global_ = desenho.ADICIONAR_NOVO_ROTULO
    assert do_cartao != global_, (
        f"os dois botões voltaram a dizer a mesma coisa ({do_cartao!r}): um é "
        f"«ele está aqui, te mostro onde» e o outro é «tem um que você não "
        f"conhece». Ela pediu um sinônimo justamente para separá-los.")
    assert do_cartao == "Localizar este Lançador", (
        f"o rótulo do botão do cartão é {do_cartao!r}, e a decisão dela é "
        f"'Localizar este Lançador' — a palavra do SELO daquele cartão")
    assert global_ == "Adicionar novo Lançador", (
        f"o rótulo do botão global é {global_!r}, e a decisão dela é "
        f"'Adicionar novo Lançador' — com o «novo», que é o que o separa do "
        f"outro")

    # A LÍNGUA. O projeto é em português e há portão que reprova inglês na tela;
    # aqui a régua alcança o rótulo ANTES de ele chegar à página publicada.
    for rotulo in (do_cartao, global_, desenho.TELA_DO_NOVO_TITULO,
                   desenho.REMOVER_ROTULO):
        assert "launcher" not in rotulo.lower(), (
            f"{rotulo!r} voltou ao inglês. A tela desta casa fala português.")

    # E O SELO E O BOTÃO FALAM A MESMA PALAVRA — é o que faz o rótulo do cartão
    # se explicar sozinho para quem lê de cima para baixo.
    assert "LOCALIZ" in desenho.SELOS["off"].upper(), (
        f"o selo do estado ausente é {desenho.SELOS['off']!r} e o botão dele diz "
        f"{do_cartao!r} — os dois deixaram de falar a mesma palavra, que era a "
        f"razão de o sinônimo ter esta forma e não outra")


def test_o_titulo_da_tela_de_registro_nao_contradiz_o_botao_que_a_abriu(desenho):
    """A CAIXA É UMA E OS CAMINHOS SÃO DOIS — e o título não pode ser de um só.

    Enquanto os dois botões diziam a mesma frase, titular a caixa com o rótulo
    do botão global era inofensivo. Com a palavra dela separando os atos, deixou
    de ser: aberta pelo botão do cartão do RetroArch, a caixa mostraria
    *«…novo…»* em cima da linha que diz que o RetroArch já tem cartão. **Duas
    células da mesma tela dizendo o contrário uma da outra.**

    O TÍTULO NEUTRO NÃO É EVASIVA — é o que o gesto FAZ nos dois caminhos: ele
    procura em disco e **recusa o que não acha** (ver
    `test_o_registro_nao_grava_o_que_nao_esta_no_disco`). Nada entra ali sem ser
    localizado, venha de onde vier.

    A MORDIDA: faça `TELA_DO_NOVO_TITULO = ADICIONAR_NOVO_ROTULO` e esta régua
    reprova; a linha de baixo continua dizendo o nome do cartão, e a tela volta
    a se contradizer.
    """
    titulo = desenho.TELA_DO_NOVO_TITULO
    assert titulo not in (desenho.ADICIONAR_ROTULO, desenho.ADICIONAR_NOVO_ROTULO), (
        f"o título da caixa é o rótulo de um dos dois botões ({titulo!r}). A "
        f"caixa é UMA e chega-se a ela por dois caminhos — metade das aberturas "
        f"mostraria um título que contradiz a linha logo abaixo.")
    assert titulo in desenho.tela_do_registro_html(), (
        "o título não chegou à marcação da tela de registro")

    # E A LINHA DE BAIXO É QUEM DIZ DE QUAL DOS DOIS SE TRATA.
    do_cartao = desenho.tela_do_registro_html(
        desenho.NOVO_PARA_O_CARTAO.format(nome="RetroArch"))
    assert "RetroArch" in do_cartao, (
        "a tela aberta pelo botão de um cartão não diz de qual cartão")
    assert desenho.NOVO_SEM_ALVO in desenho.tela_do_registro_html(), (
        "a tela aberta pelo botão global perdeu a linha que diz o que ela é")

    # O ARTIGO SAIU DA FRASE, e foi a foto que mostrou: com o cartão da Steam
    # ganhando o botão, «Onde está O Steam» chegou à tela — e esta casa escreve
    # «a Steam» em toda a aba. A frase sem artigo vale para todo nome, inclusive
    # os que ela ainda vai inventar no cartão novo.
    for nome in ("Steam", "RetroArch", "Dolphin · mGBA"):
        linha = desenho.NOVO_PARA_O_CARTAO.format(nome=nome)
        assert not linha.lower().startswith(("o ", "a ")), linha
        assert f" o {nome}" not in linha and f" a {nome}" not in linha, (
            f"a linha voltou a pôr artigo antes do nome do cartão: {linha!r}. "
            f"Os nomes têm gêneros diferentes e um deles vem do teclado dela — "
            f"adivinhar o artigo é palpite na tela.")


def test_a_contagem_do_topo_conta_presenca_e_nao_selo(desenho):
    """`N encontrados` responde "quantos estão aqui", não "em quantos eu sei".

    A MORDIDA: volte `Quadro.achados` para `x.selo in ("ok", "warn")` e o
    lançador achado some da conta enquanto o cartão dele continua dizendo
    "achei este lançador aqui" — duas afirmações opostas na mesma tela.
    """
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("heroic", "h.desktop"), ("lutris", "")))
    quadro = desenho.Quadro(lancadores=desenho.cartoes(lida))
    assert quadro.achados == 2, (
        f"a Steam e o Heroic estão aqui e a conta diz {quadro.achados}")
    assert "2 encontrados" in desenho.conta_html(quadro.achados, quadro.impedidos)


def test_nenhuma_fileira_de_botoes_vira_travessao(desenho):
    """Fileira vazia não pode virar `—` na tela. Fotografado em 02/09/2026.

    O `escrever()` do bootstrap troca vazio por travessão — certo para um campo
    de valor, errado para um contêiner de HTML. Enquanto a raiz não é curada
    (`hefesto_vivo.py`, fora do território desta aba), o desenho não pode emitir
    string vazia num alvo `html`.

    NENHUM CARTÃO CHEGA A ESTE ESTADO HOJE, e é por isso que a régua mede a
    FUNÇÃO e não um cartão: desde a decisão dela de 02/09 os seis cartões têm
    pelo menos um botão. A guarda fica porque `acoes_html` é pública e o dia em
    que um cartão nascer sem fileira o traço volta calado — foi assim que ele
    apareceu em quatro cartões de uma vez.
    """
    vazio = desenho.acoes_html(
        desenho.Lancador(chave="x", nome="X", selo="off", jogos="—", diz=""))
    assert vazio, "a fileira vazia voltou a ser string vazia — a tela mostra `—`"
    assert "<button" not in vazio, "a fileira sem ações inventou um botão"
    assert vazio.strip().startswith("<!--"), (
        f"a fileira vazia virou texto na tela: {vazio!r}")

    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = desenho.valores_do_cartao(desenho.cartao_da_steam(lida))
    assert steam["steam-fora"], (
        "a lista vazia da Steam voltou a ser string vazia — era o traço solto "
        "no pé do cartão, que estava lá desde 02/09 de manhã")


def test_a_lista_da_steam_nunca_vira_travessao_em_estado_nenhum(desenho):
    """Os TRÊS estados do cartão, e não só o que já estava curado.

    A CURA ANTERIOR ALCANÇOU UM SÓ. `lista_de_jogos` ganhou `LISTA_VAZIA`, mas
    os dois ramos de saída antecipada de `cartao_da_steam` — a primeira meia
    volta e a Steam ilegível — devolviam `fora=""` com `tem_lista=True`. O
    `escrever()` do bootstrap troca vazio por `—` **antes** de despachar o alvo
    `html`, e o da Steam ilegível é PERMANENTE: justo a tela em que ela precisa
    ler uma mensagem, com um traço mudo pendurado embaixo.

    A MORDIDA: tire o `fora=SEM_LISTA` de qualquer um dos dois ramos e este
    teste reprova nomeando o estado.
    """
    estados = {
        "primeira meia volta": None,
        "Steam ilegível": desenho.Leitura(erros=("o vdf ficou ilegível",)),
        "leitura boa, lista vazia": desenho.Leitura(com_wrapper=("1",),
                                                    instalados=1),
    }
    for nome, lida in estados.items():
        cartao = desenho.cartao_da_steam(lida)
        valor = desenho.valores_do_cartao(cartao)["steam-fora"]
        assert valor != "", (
            f"o cartão da Steam em '{nome}' emite `steam-fora` VAZIO — o "
            f"bootstrap o troca por `—` e a tela ganha um traço solto no pé")

    # E A LISTA NÃO PODE AFIRMAR O QUE NINGUÉM LEU: nos dois estados sem
    # leitura, o que vai para a tela é NADA (um comentário HTML), e não a frase
    # de "nenhum jogo com pendência" — que seria o resultado de uma leitura que
    # não aconteceu.
    for nome in ("primeira meia volta", "Steam ilegível"):
        valor = desenho.valores_do_cartao(
            desenho.cartao_da_steam(estados[nome]))["steam-fora"]
        assert valor.strip().startswith("<!--"), (
            f"o cartão em '{nome}' escreve texto na lista: {valor!r}")
        assert "pendência" not in valor, (
            f"o cartão em '{nome}' afirma o resultado de uma leitura que não "
            f"aconteceu")


def test_a_moldura_do_cartao_segue_o_selo_que_o_produto_mediu(a07, ctx, desenho,
                                                              monkeypatch):
    """A borda do cartão e o selo dentro dele não podem discordar.

    FOTOGRAFADO EM 02/09/2026: a `MOLDURA` só era escrita por `um_cartao`, que é
    o GERADOR. A página publicada nasceu com os seis cartões em `class="lanc
    ausente"` (o estado `cartoes(None)`) e o pacote não emitia a classe do
    contêiner — cinco endereços por cartão, nenhum deles a moldura. O cartão da
    Steam mostrava o selo verde `CHEGAM` numa borda cinza de *ausente*: a mesma
    tela dizendo duas coisas opostas.

    A MORDIDA: tire o `blocos` de `_pintura` (ou aponte-o para um seletor que a
    página não tem) e este teste reprova nos dois lados — a grade some da carga,
    ou ela é escrita num lugar que `querySelector` não acha.
    """
    # 1. o seletor tem de EXISTIR na página, senão o bloco é escrito no nada
    assert f'class="{desenho.CLASSE_DA_GRADE}"' in _bancada(), (
        f"a página não tem a grade `{desenho.SELETOR_DA_GRADE}` — o `blocos` "
        f"cairia no chão, e `querySelector` devolve `null` sem uma linha de erro")

    # 2. a carga do tique traz a grade.
    #    A VIGIA VAI DUBLADA: sem isso, `pacote()` dispara a thread que lê o
    #    disco DELA, e essa leitura cai dentro da janela de outra régua deste
    #    mesmo arquivo (medido em 02/09/2026 — o espião do `anotar=False` viu
    #    duas chamadas). Uma régua que acorda o disco de outra é ruído.
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    carga = a07.pacote(ctx)
    grade = (carga.get("blocos") or {}).get(desenho.SELETOR_DA_GRADE)
    assert grade, (
        "o pacote não manda a grade — a classe do contêiner fica a do desenho "
        "para sempre, e o cartão se pinta como outra coisa do que mede")

    # 3. e a moldura de cada cartão é a que o SELO pede
    lida = desenho.Leitura(com_wrapper=("1", "2"), instalados=23,
                           reparaveis=(),
                           onde_estao=(("heroic", ""), ("lutris", "")))
    cartoes = desenho.cartoes(lida)
    html = a07._pintura(cartoes)["blocos"][desenho.SELETOR_DA_GRADE]
    assert cartoes[0].selo == "ok", "a Leitura da régua deixou de ser a `CHEGAM`"
    assert f'class="lanc {desenho.MOLDURA["ok"]}" data-lancador="steam"' in html, (
        "a Steam mede `CHEGAM` e a moldura dela continua a de `ausente` — é o "
        "cartão dizendo duas coisas opostas na mesma tela")

    quebrada = desenho.cartoes(desenho.Leitura(
        com_wrapper=("1",), instalados=2,
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),),
        frase="alguma frase"))
    html_warn = a07._pintura(quebrada)["blocos"][desenho.SELETOR_DA_GRADE]
    assert f'class="lanc {desenho.MOLDURA["warn"]}" data-lancador="steam"' in (
        html_warn), (
        "a Steam mede `NÃO CHEGAM` e a borda não fica laranja — a única coisa "
        "que esta aba mostra sem ler é a cor")


def test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa(a07, desenho):
    """As duas grafias do mesmo valor têm de ser UMA — senão a tela pinga-pongue.

    O DEFEITO, MEDIDO NA TELA em 02/09/2026 com o piloto rodando 40 segundos: o
    gerador escrevia a fileira de botões dentro de `<div class="acoes">` com
    quebra de linha e recuo, e o pacote pintava o MESMO valor sem eles. Enquanto
    a grade não era repintada ninguém via; com ela virando bloco, os dois lados
    passaram a se corrigir mutuamente **em 81 de 81 voltas** — duas reescritas
    por segundo, para sempre, matando o foco e o `:hover` de quem estivesse com
    o mouse num botão.

    O `escrever()` do piloto só escreve quando `innerHTML !== valor`; o `blocos`
    só troca quando `innerHTML !== html`. As duas comparações são de TEXTO
    LITERAL — então um espaço de diferença é uma reescrita eterna.

    A MORDIDA: devolva a quebra de linha para `um_cartao` (ou tire-a de
    `acoes_html`) e este teste reprova nomeando o campo.
    """
    lida = desenho.Leitura(
        com_wrapper=("1",), instalados=3, frase="alguma frase",
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),),
        recusados=(("9", "Outro jogo"),),
        onde_estao=(("heroic", "/x/h.desktop"), ("lutris", "")))
    cartoes = desenho.cartoes(lida)
    grade = a07._pintura(cartoes)["blocos"][desenho.SELETOR_DA_GRADE]
    valores = desenho.Quadro(lancadores=cartoes).valores()

    for chave, valor in valores.items():
        if chave == "lanc-conta":  # mora no topo do quadro, fora da grade
            continue
        assert f">{valor}<" in grade, (
            f"o campo {chave!r} é pintado com uma grafia e a grade traz outra. "
            f"As duas se corrigem a cada tique, para sempre — foi assim que o "
            f"piloto contou pintura em 81 de 81 voltas.")


# --------------------------------------------------------------------------
# 6b. O LAÇO INFINITO: a marcação tem de VOLTAR IGUAL do DOM
#
# O piloto só reescreve quando `innerHTML !== valor` (`hefesto_vivo.py:160` no
# campo, `:303` no bloco). O lado esquerdo é o que o DOM **devolve**, não o que
# se escreveu — então uma grafia que o DOM normaliza nunca casa, e a reescrita
# não para NUNCA: 2 por segundo, para sempre, matando o foco e o `:hover` de
# quem estiver com o mouse num botão.
#
# `test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa` NÃO ALCANÇA ISTO:
# ele compara os dois lados PYTHON, e os dois estão igualmente errados. O que
# falta é o terceiro lado — o DOM.
# --------------------------------------------------------------------------
#: AS TAGS QUE NÃO TÊM FECHAMENTO. Nenhuma aparece nos cartões hoje; a lista
#: existe para o instrumento não inventar um `</br>` no dia em que uma aparecer.
_VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
           "meta", "source", "track", "wbr"}


def _como_o_dom_devolve(marcacao: str) -> str:
    """Reserializa a marcação pelas regras que o WEBKIT DELA usa. É medida.

    A TABELA NÃO FOI DEDUZIDA DA ESPECIFICAÇÃO — foi MEDIDA em 02/09/2026 no
    WebKit da janela do produto, com um `<div>` solto recebendo `innerHTML` e
    devolvendo `innerHTML`, para os seis caracteres nas duas grafias (28 casos):

        ==========  ==================  ==================
        caractere   em TEXTO            em ATRIBUTO
        ==========  ==================  ==================
        ``&``       ``&amp;``           ``&amp;``
        ``<``       ``&lt;``            ``&lt;``
        ``>``       ``&gt;``            ``&gt;``
        U+00A0      ``&nbsp;``          ``&nbsp;``
        ``"``       **cru**             ``&quot;``
        ``'``       **cru**             **cru**
        ==========  ==================  ==================

    O `<` e o `>` no atributo surpreendem — a especificação de serialização não
    os manda escapar, e o WebKit escapa. É exatamente por isso que a tabela é
    medida e não lembrada: um instrumento que seguisse a especificação diria que
    `data-v="a&lt;b"` pinga-pongue, e ele não pinga.
    """
    from html.parser import HTMLParser

    def texto(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("\u00a0", "&nbsp;"))

    def atributo(s: str) -> str:
        return texto(s).replace('"', "&quot;")

    class _Volta(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.fora: list[str] = []

        def handle_starttag(self, tag, attrs):
            pedacos = "".join(
                f" {n}" if v is None else f' {n}="{atributo(v)}"'
                for n, v in attrs)
            self.fora.append(f"<{tag}{pedacos}>")

        handle_startendtag = handle_starttag

        def handle_endtag(self, tag):
            if tag not in _VAZIAS:
                self.fora.append(f"</{tag}>")

        def handle_data(self, data):
            self.fora.append(texto(data))

        def handle_comment(self, data):
            self.fora.append(f"<!--{data}-->")

    leitor = _Volta()
    leitor.feed(marcacao)
    leitor.close()
    return "".join(leitor.fora)


#: OS NOMES QUE QUEBRAM O ROUND-TRIP, e nenhum é inventado: o apóstrofo está em
#: `Assassin's Creed` e em `Marvel's Spider-Man`; a aspa e o `&` aparecem em
#: título de demo e de coletânea. A biblioteca dela tem 63 aplicativos com a
#: linha de inicialização — basta UM.
_NOMES_QUE_MORDEM = ("Assassin's Creed", 'O jogo "bom"', "Ratchet & Clank",
                     "a < b > c", "espa\u00e7o\u00a0duro", "Tom Clancy's")


@pytest.mark.parametrize("nome", _NOMES_QUE_MORDEM)
def test_a_marcacao_volta_igual_do_dom(a07, desenho, nome):
    """Um apóstrofo no nome de UM jogo reescrevia a GRADE INTEIRA, para sempre.

    MEDIDO NA JANELA em 02/09/2026, com o piloto oculto e a MESMA carga pintada
    seis vezes seguidas (uma pintura idempotente devolve 0 da segunda em
    diante):

        nome sem apóstrofo   →  2, 1, 1, 1, 1, 1
        `Assassin's Creed`   →  2, 2, 2, 2, 2, 2

    O `1` que sobra em todas as voltas é OUTRO defeito, do piloto, e está
    relatado (`data-hef-visto`, `hefesto_vivo.py:150`). O `+1` do apóstrofo é
    deste arquivo: `html.escape(quote=True)` emitia `&#x27;` e o DOM devolvia
    `'`. As duas grafias se corrigiam eternamente.

    A MORDIDA: devolva o `quote=True` ao `_e` (ou tire o `.replace('"', ...)`
    do `_a`) e este teste reprova nomeando o trecho.
    """
    lida = desenho.Leitura(
        com_wrapper=("1",), instalados=3, frase="alguma frase",
        reparaveis=((f"2{nome}", nome, "nunca recebeu o atalho"),),
        recusados=(("9", nome),),
        dispensados=(("7", nome),),
        onde_estao=(("heroic", f"/casa/{nome}/h.desktop"), ("lutris", "")))
    cartoes = desenho.cartoes(lida)
    carga = a07._pintura(cartoes)

    alvos = {desenho.SELETOR_DA_GRADE: carga["blocos"][desenho.SELETOR_DA_GRADE]}
    alvos.update({k: v for k, v in carga["mesa"].items()
                  if k.endswith(("-selo", "-diz", "-acoes", "-fora"))})

    for onde, marcacao in alvos.items():
        volta = _como_o_dom_devolve(marcacao)
        assert volta == marcacao, (
            f"{onde} não volta igual do DOM com o nome {nome!r}. O piloto "
            f"compara `innerHTML !== valor` como TEXTO, então ele reescreve "
            f"este elemento a CADA TIQUE, para sempre — 2 por segundo, "
            f"matando o foco e o `:hover` de quem estiver com o mouse num "
            f"botão.\n  emitido: {marcacao[:160]!r}\n  do DOM:  {volta[:160]!r}")


def test_o_instrumento_do_round_trip_morde(desenho):
    """A régua acima só vale se ela souber reprovar. Aqui está a prova.

    Um instrumento que devolvesse a entrada intacta daria VERDE sobre qualquer
    grafia — e seria o quinto instrumento falso desta casa. Estas quatro linhas
    são as quatro células medidas que separam texto de atributo.
    """
    assert _como_o_dom_devolve("<b>a&#x27;b</b>") == "<b>a'b</b>"
    assert _como_o_dom_devolve("<b>a&quot;b</b>") == '<b>a"b</b>'
    assert _como_o_dom_devolve('<b x="a&#x27;b"></b>') == '<b x="a\'b"></b>'
    assert _como_o_dom_devolve('<b x="a&quot;b"></b>') == '<b x="a&quot;b"></b>'
    assert _como_o_dom_devolve("<b>a\u00a0b</b>") == "<b>a&nbsp;b</b>"
    # e o que JÁ estava certo continua certo — senão a régua acusaria a cura
    assert _como_o_dom_devolve("<b>a&amp;b</b>") == "<b>a&amp;b</b>"
    assert _como_o_dom_devolve('<b x="a&lt;b"></b>') == '<b x="a&lt;b"></b>'
    assert _como_o_dom_devolve("<!-- nada -->") == "<!-- nada -->"


# --------------------------------------------------------------------------
# 7. as duas leituras do disco que tela NENHUMA mostrava
# --------------------------------------------------------------------------
def test_os_jogos_dispensados_do_lembrete_aparecem_na_lista(desenho):
    """O `launch_dialog_dismissed.json` ganha a primeira tela da casa — E A VOLTA.

    A escrita tinha dono (o botão "Não perguntar para este jogo" do lembrete da
    GTK) e a LEITURA não tinha nenhuma: clicar produzia um silêncio permanente
    que ninguém podia consultar depois.

    A LINHA GANHOU BOTÃO EM 02/09/2026, por decisão dela — e ele só pôde nascer
    porque `launch_wrapper_dialog` ganhou o `remove_dismissed_appid` que lhe
    faltava. Esta régua guarda os dois lados: a linha tem de mostrar o botão, e
    o botão tem de apontar para um gesto com dono. Um `data-gesto` que ninguém
    atende some no clique.
    """
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           dispensados=(("4242", "Jogo Dispensado"),))
    fora = desenho.valores_do_cartao(
        desenho.cartao_da_steam(lida))["steam-fora"]
    assert "Jogo Dispensado" in fora and "não perguntar mais" in fora, (
        "o jogo dispensado não aparece na lista do cartão da Steam")
    assert 'data-gesto="voltar-a-perguntar" data-v="4242"' in fora, (
        "a linha do dispensado voltou a ser um beco sem saída — dispensar "
        "é um gesto sem volta pela tela, e a única saída era editar o "
        "`launch_dialog_dismissed.json` à mão")
    assert "Voltar a perguntar" in fora, "o botão da linha ficou sem rótulo"
    _gesto("voltar-a-perguntar")  # ele existe e tem dono, ou isto levanta


def test_voltar_a_perguntar_escreve_no_arquivo_de_verdade(ctx):
    """O par completo da dispensa, contra o JSON do lar de mentira.

    O `conftest.py` desta casa desvia `HOME` e os quatro `XDG_*`, então este
    teste escreve num arquivo temporário — nunca no dela. É a prova mais forte
    que este botão pode ter: não *"a função foi chamada"*, mas **o arquivo
    mudou**.

    A MORDIDA: troque o corpo de `remove_dismissed_appid` por `return True` e
    este teste reprova — o botão diria que desfez, e o jogo continuaria
    dispensado para sempre.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    assert lwd.load_dismissed_appids() == set(), "o lar de mentira nasceu sujo"

    lwd.add_dismissed_appid("1070560")
    assert "1070560" in lwd.load_dismissed_appids()

    _gesto("voltar-a-perguntar")(ctx, {"v": "1070560"}, None)
    assert "1070560" not in lwd.load_dismissed_appids(), (
        "o gesto disse que aplicou e o `launch_dialog_dismissed.json` continua "
        "com o appid — o lembrete fica desligado para sempre")


def test_voltar_a_perguntar_recusa_dizendo_quando_o_arquivo_nao_aceita(
        ctx, monkeypatch):
    """Um clique que falha calado é o defeito mais caro desta casa.

    `add_dismissed_appid` engole a falha de propósito (roda no tique, e o pior
    caso é o lembrete voltar uma vez). O `remove` roda no CLIQUE DELA: se ele
    engolisse, a linha continuaria na tela e o segundo clique pareceria o
    primeiro. Por isso ele devolve `bool` e o gesto levanta `RuntimeError`.

    A MORDIDA: faça `remove_dismissed_appid` devolver `None` sempre e o gesto
    parar de conferir — este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    monkeypatch.setattr(lwd, "remove_dismissed_appid", lambda a: False)
    with pytest.raises(RuntimeError, match="dispensados"):
        _gesto("voltar-a-perguntar")(ctx, {"v": "4242"}, None)


def test_remover_um_appid_que_nao_estava_na_lista_devolve_falso():
    """`False` também quando não havia o que remover — e é a mesma verdade.

    Para quem clicou, *"o arquivo não aceitou"* e *"o appid já não estava lá"*
    dizem a mesma coisa: **nada mudou por causa deste clique**. Devolver `True`
    aqui faria a tela dizer que desfez algo que ela não desfez.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    assert lwd.remove_dismissed_appid("999999") is False
    lwd.add_dismissed_appid("111")
    assert lwd.remove_dismissed_appid("111") is True
    assert lwd.remove_dismissed_appid("111") is False, (
        "o segundo clique na mesma linha disse que desfez de novo")


def test_a_ponte_confirmada_volta_ao_carimbo(desenho):
    """`◆ N jogos já sabem por onde entrar` — a promessa que estava sem fonte.

    O HTML de 02/09 dizia `◆ 3 jogos já sabem por onde entrar` com o número
    DIGITADO, e `prontuario_dos_jogos.pontes_confirmadas` respondia a mesma
    pergunta sem nenhum chamador.
    """
    sem = desenho.Leitura(com_wrapper=("1",), instalados=1)
    assert desenho.carimbo_da_steam(sem) == "", (
        "zero pontes ocupou a linha do carimbo para não dizer nada")

    com = desenho.Leitura(com_wrapper=("1",), instalados=1, pontes=3,
                          intocaveis=(("9", "Jogo", "linha à mão"),))
    carimbo = desenho.carimbo_da_steam(com)
    assert "3 jogos já sabem por onde entrar" in carimbo, (
        f"a ponte confirmada sumiu do carimbo: {carimbo!r}")
    assert "intocável" in carimbo, (
        "o carimbo calou sobre o jogo que o produto decidiu não tocar — é "
        "assim que ele fica sem o atalho para sempre sem ninguém saber")


def _disco_dublado(monkeypatch, *, dispensados=("4242",), pontes=3,
                   instalados=7):
    """Todo o disco que `_ler_do_disco` toca, dublado — e nada da máquina dela.

    ELE EXISTE PORQUE AS DUAS RÉGUAS DE CIMA PROVAM O DESENHO, e não o
    CHAMADOR: `test_os_jogos_dispensados_do_lembrete_aparecem_na_lista` e
    `test_a_ponte_confirmada_volta_ao_carimbo` montam uma `Leitura` À MÃO.
    Medido em 02/09/2026 pela auditoria desta aba: arrancar
    `dispensados=_dispensados()` e `pontes=pontes` de `_ler_do_disco` deixava
    as 25 réguas VERDES — e trocar `pontes_confirmadas()` por
    `jogos_instalados()` também, com o carimbo voltando a mostrar um número sem
    fonte (`◆ 23 jogos já sabem por onde entrar` onde a resposta é ZERO).

    É *"cura escrita, testada, e nunca ligada"*, que esta casa já nomeou.

    OS TRÊS NÚMEROS SÃO DIFERENTES DE PROPÓSITO (7 instalados, 3 pontes, 1
    dispensado): com dois iguais, uma fonte trocada pela outra passaria.
    """
    import types

    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    censo = types.SimpleNamespace(com_wrapper=["1"], reparaveis=[],
                                  intocaveis=[], recusados=[], erros=[])
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **kw: censo)
    monkeypatch.setattr(sw, "frase_do_aviso", lambda c: "")
    monkeypatch.setattr(pdj, "jogos_instalados", lambda: list(range(instalados)))
    monkeypatch.setattr(pdj, "pontes_confirmadas", lambda: list(range(pontes)))
    monkeypatch.setattr(lwd, "load_dismissed_appids", lambda: set(dispensados))
    monkeypatch.setattr(slo, "rotulo_do_jogo", lambda a: f"Jogo {a}")


def test_a_leitura_carrega_os_dispensados_e_as_pontes_da_fonte_certa(
        a07, monkeypatch, tmp_path):
    """As duas leituras novas do motor, cobradas em QUEM AS CHAMA.

    AS TRÊS MORDIDAS QUE ESTE TESTE MATA, e as três davam 25/25 verde antes
    dele:

    ==========================================  ===========================
    `dispensados=_dispensados()` → `()`         a lista do cartão esvazia
    `pontes=pontes` → `0`                       o carimbo some
    `pontes_confirmadas()` → `jogos_instalados()`  o carimbo mente o número
    ==========================================  ===========================

    A terceira é a pior: ela REINTRODUZ o defeito que a aba nasceu para matar —
    um número no carimbo que não responde à pergunta do carimbo.
    """
    _pastas_falsas(monkeypatch, tmp_path)
    _disco_dublado(monkeypatch, dispensados=("4242",), pontes=3, instalados=7)

    lida = a07._ler_do_disco()
    assert lida.dispensados == (("4242", "Jogo 4242"),), (
        f"a leitura do disco não carrega os jogos dispensados do lembrete: "
        f"{lida.dispensados!r} — o `launch_dialog_dismissed.json` volta a ser "
        f"um silêncio que tela nenhuma mostra")
    assert lida.pontes == 3, (
        f"a leitura do disco diz {lida.pontes} pontes e a fonte respondeu 3 — "
        f"o carimbo `◆ N jogos já sabem por onde entrar` voltou a ter um "
        f"número sem fonte, que é o defeito que esta aba nasceu para matar")
    assert lida.instalados == 7, "a contagem de instalados trocou de fonte"

    # E O QUE SAI DISSO CHEGA À TELA — sem esta metade, as três mordidas de
    # cima morrem e uma quarta (a `Leitura` montada e jogada fora) passa.
    valores = a07._valores(lida)
    assert "3 jogos já sabem por onde entrar" in valores["steam-diz"] + (
        valores["steam-acoes"]), (
        "as pontes chegaram à leitura e não chegaram ao carimbo do cartão")
    assert "Jogo 4242" in valores["steam-fora"], (
        "o jogo dispensado chegou à leitura e não chegou à lista do cartão")


def test_a_contagem_do_topo_nao_cai_depois_do_gesto(a07, monkeypatch, desenho):
    """`_com_outra_frase` não pode devolver um cartão com campo perdido.

    O SINTOMA, MEDIDO: com o construtor à mão dos nove campos no lugar do
    `dataclasses.replace`, o décimo campo (`presente`) volta ao padrão e a
    contagem do topo CAI de "2 encontrados" para "1 encontrado" **depois** de
    ela clicar em "Detectar o jogo que está aberto" ou em "Ver o que impede" —
    com os seis cartões inalterados, e nada acusando.

    A cura estava escrita desde 02/09 e **não tinha régua**: a auditoria
    reverteu a linha para o texto exato de antes e as 25 passaram.

    A MORDIDA: troque o `dataclasses.replace` pelo construtor campo a campo e
    este teste reprova comparando as duas contagens.
    """
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("heroic", "h.desktop"), ("lutris", "")))
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: lida)

    do_tique = a07._valores(lida)["lanc-conta"]
    do_gesto = a07._com_outra_frase("uma frase qualquer")["mesa"]["lanc-conta"]

    assert "2 encontrados" in do_tique, (
        f"a régua perdeu o pé: a pintura do tique já não conta 2 ({do_tique!r})")
    assert do_gesto == do_tique, (
        f"a contagem do topo MUDA depois do gesto — o tique diz {do_tique!r} e "
        f"o gesto devolve {do_gesto!r}. A tela discorda de si mesma sem que "
        f"nenhum cartão tenha mudado.")

    # E O CARTÃO TROCADO CONTINUA SENDO O DA STEAM, com tudo o que ele tinha —
    # um `replace` que perdesse `tem_lista` apagaria a lista de jogos inteira.
    assert a07._com_outra_frase("outra")["mesa"]["steam-fora"], (
        "o cartão trocado perdeu a lista de jogos")


def test_a_steam_quebrada_nao_apaga_a_resposta_sobre_os_outros(a07, monkeypatch,
                                                               tmp_path):
    """Duas perguntas independentes não podem cair juntas.

    A MORDIDA: mova o `_onde_estao_os_lancadores()` para DEPOIS do `try` do
    censo e este teste reprova — um `localconfig.vdf` ilegível apagaria a
    resposta sobre o Heroic, que não tem nada com a Steam.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    pasta = _pastas_falsas(monkeypatch, tmp_path, "net.lutris.Lutris")

    def explode(*a, **kw):
        raise OSError("o vdf sumiu")

    monkeypatch.setattr(sw, "censo_do_wrapper", explode)
    lida = a07._ler_do_disco()
    assert lida.erros, "o censo quebrou e a leitura não registrou o erro"
    assert dict(lida.onde_estao)["lutris"] == str(
        pasta / "net.lutris.Lutris.desktop"), (
        "a Steam quebrada apagou a resposta sobre os outros lançadores")


# --------------------------------------------------------------------------
# 10. a PRESENÇA da Steam — o sexto cartão entra na medição
#
# NASCEU EM 02/09/2026, À NOITE, de uma acusação provada antes de curada. A
# busca por `.desktop` + `PATH` nasceu à tarde percorrendo `SEM_FONTE`, que é a
# lista de *"não sei ler a biblioteca dele"* — e a Steam não está nela porque o
# produto LÊ a biblioteca dela. Só que ter censo do INTERIOR não responde se o
# lançador está AQUI, e o cartão da Steam nascia com `presente=True` cravado.
#
# Medido antes da cura, com o `HOME` numa casa de mentira, `PATH` sem binário e
# `pastas_de_atalhos` numa pasta vazia:
#
#     conta do topo   "1 encontrado · 0 com impedimentos"
#     steam           selo 'ok' (CHEGAM) · presente True
#                     "Os controles chegam. O atalho de inicialização está no
#                      lugar em 0 jogos da sua biblioteca."
#     os outros cinco selo 'off' (NÃO ACHEI)
#
# O selo VERDE sobre uma máquina sem Steam nenhuma, na mesma tela em que os
# cinco vizinhos diziam NÃO ACHEI — a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor
# verde, que é a frase com que esta aba nasceu.
# --------------------------------------------------------------------------
def test_a_steam_ausente_nao_afirma_que_os_controles_chegam(a07, desenho,
                                                            monkeypatch,
                                                            tmp_path):
    """O CAMINHO INTEIRO: busca vazia → leitura → cartão → conta do topo.

    A MORDIDA: volte `_onde_estao_os_lancadores` a percorrer `desenho.SEM_FONTE`
    (ou devolva `presente=True` cravado no fim de `cartao_da_steam`) e este
    teste reprova nomeando o selo verde.

    ELE MEDE O CHAMADOR, e não só a função: arrancar a cura no `_ler_do_disco`
    deixaria uma régua que só chamasse `cartao_da_steam` à mão VERDE sobre uma
    tela que voltou a mentir — *"cura escrita, testada, e nunca ligada"*.
    """
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    _pastas_falsas(monkeypatch, tmp_path)  # pasta VAZIA, `PATH` sem binário

    # Nenhuma biblioteca: é o par honesto de "não achei o lançador". Sem isto o
    # teste dependeria do `HOME` de quem o roda — e na máquina dela há 63
    # appids com o wrapper, que fariam a régua medir a bancada, não a cura.
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **kw: sw.Censo())
    monkeypatch.setattr(pdj, "jogos_instalados", lambda *a, **kw: [])
    monkeypatch.setattr(pdj, "pontes_confirmadas", lambda *a, **kw: [])

    lida = a07._ler_do_disco()
    assert dict(lida.onde_estao).get("steam") == "", (
        f"a busca não procurou a Steam: {dict(lida.onde_estao)}. O cartão dela "
        f"volta a afirmar por constante.")
    assert not lida.viu_a_biblioteca, (
        "o dublê deixou passar uma biblioteca — a régua mediria a bancada")

    cartao = desenho.cartao_da_steam(lida)
    # LÊ O SELO, NÃO A PALAVRA — a razão inteira está em
    # `test_o_cartao_achado_e_o_nao_achado_dizem_coisas_diferentes`.
    assert cartao.selo == "off", (
        f"sem Steam nenhuma nesta máquina o cartão diz "
        f"{desenho.SELOS.get(cartao.selo)!r} — o selo verde sobre o vazio é a "
        f"mentira que esta aba existe para não contar")
    assert not cartao.presente, "a Steam que não está aqui conta como encontrada"
    assert "chegam" not in cartao.diz.lower(), (
        f"o corpo do cartão promete que os controles chegam: {cartao.diz!r}")

    quadro = desenho.Quadro(lancadores=desenho.cartoes(lida))
    assert quadro.achados == 0, (
        f"o topo diz {quadro.achados} encontrado(s) numa máquina sem lançador "
        f"nenhum")
    assert "0 encontrados" in a07._valores(lida)["lanc-conta"], (
        "a conta chegou certa ao quadro e errada à tela")


def test_a_steam_sem_procura_e_sem_biblioteca_nao_conta_como_encontrada(desenho):
    """O CONTRATO do `presente`, e esta régua nasceu de uma mordida que FALHOU.

    Trocar o `presente=bool(...) or ...` do fim de `cartao_da_steam` de volta
    pelo `presente=True` cravado deixou as 46 VERDES — porque o ramo do `NÃO
    ACHEI` já intercepta o caso que a tela alcança, e a constante só sobrevive
    onde nada a contradiz. Uma cura sem régua é uma cura que volta atrás calada,
    e foi assim que o `presente` virou constante da primeira vez.

    O ESTADO QUE ELA COBRE: uma `Leitura` que **não procurou** (a `steam` fora
    do mapa) e **não leu nada**. A tela não chega nele — `_ler_do_disco` sempre
    preenche o mapa —, mas `cartao_da_steam` é público e a régua desta aba monta
    `Leitura` à mão o tempo todo. Uma constante aqui responde *"encontrada"*
    sobre uma leitura que não mediu nem leu coisa alguma.
    """
    cartao = desenho.cartao_da_steam(desenho.Leitura())
    assert not cartao.presente, (
        "o `presente` do cartão da Steam voltou a ser constante: uma leitura "
        "que não procurou nada e não leu nada conta como lançador encontrado")


def test_a_steam_que_esta_aqui_continua_respondendo_pelo_censo(a07, desenho,
                                                               monkeypatch,
                                                               tmp_path):
    """A MESA DELA não pode mudar: achada, o cartão volta a ser o de sempre.

    A Steam está em `/usr/local/share/applications/steam.desktop` na bancada
    dela — a cura tem de ser invisível ali. Uma régua que só provasse o NÃO
    ACHEI daria verde sobre uma cura que apagou o cartão dela.
    """
    _pastas_falsas(monkeypatch, tmp_path, "steam")
    lida = desenho.Leitura(
        com_wrapper=("1", "2"), instalados=2,
        onde_estao=tuple(a07._onde_estao_os_lancadores()))
    cartao = desenho.cartao_da_steam(lida)
    assert desenho.SELOS[cartao.selo] == "CHEGAM" and cartao.presente, (
        f"a Steam ACHADA e com a biblioteca lida perdeu o cartão de sempre: "
        f"{desenho.SELOS[cartao.selo]!r}")
    assert "2 jogos instalados" in cartao.jogos


def test_a_steam_fora_das_tres_buscas_nao_apaga_a_biblioteca_lida(desenho):
    """As DUAS perguntas discordando: não achei o lançador, mas li a biblioteca.

    Uma Steam instalada por um caminho que os três `.desktop` conhecidos não
    cobrem (um AppImage, um script no `~/bin`) não aparece na procura — e o
    `localconfig.vdf` dela está lá, com a biblioteca inteira. Dizer `NÃO ACHEI`
    sobre uma biblioteca recém-lida seria trocar um erro por outro.

    A MORDIDA: tire o `and not lida.viu_a_biblioteca` do ramo novo de
    `cartao_da_steam` e este teste reprova.
    """
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("steam", ""),))
    cartao = desenho.cartao_da_steam(lida)
    assert desenho.SELOS[cartao.selo] == "CHEGAM", (
        "o produto leu 1 jogo da biblioteca e o cartão diz que não achou a "
        "Steam — a tela discorda de si mesma")
    assert cartao.presente, (
        "a biblioteca foi lida e o topo não conta a Steam como encontrada")

    # E O VDF ILEGÍVEL TAMBÉM É PROVA DE QUE ELA EXISTE — um erro de leitura
    # não pode virar "não achei", que é a resposta de quem não tem o arquivo.
    quebrada = desenho.Leitura(erros=("o vdf sumiu",), onde_estao=(("steam", ""),))
    assert "Não consegui ler a biblioteca da Steam" in (
        desenho.cartao_da_steam(quebrada).diz), (
        "um vdf ilegível virou 'não achei este lançador' — some a mensagem que "
        "ela precisa ler")


def test_o_cartao_da_steam_nao_achada_mantem_os_enderecos_da_pagina(desenho):
    """O estado novo não pode tirar um endereço da página publicada.

    O PORTÃO DOS DOIS MUNDOS em miniatura: `steam-fora` existe no HTML dela e é
    pintado sempre. Um cartão novo com `tem_lista=False` deixaria o `<div>` com
    o desenho para sempre — e a régua da aba (`test_todo_endereco_da_pagina_tem
    _quem_o_pinte`) só olha o estado `cartoes(None)`.
    """
    lida = desenho.Leitura(onde_estao=(("steam", ""),))
    cartao = desenho.cartao_da_steam(lida)
    assert cartao.tem_lista, (
        "o cartão da Steam não achada deixou de emitir `steam-fora` — o `<div>` "
        "da página fica com o desenho e ninguém vê")
    campos = desenho.valores_do_cartao(cartao)
    esperados = {f"steam{s}" for s in desenho.SUFIXOS} | {
        f"steam{desenho.SUFIXO_DA_LISTA}"}
    assert set(campos) == esperados, (
        f"o estado novo emite {sorted(campos)} e a página tem "
        f"{sorted(esperados)}")
    assert campos["steam-fora"] == desenho.SEM_LISTA, (
        "a lista vazia voltou a ser string vazia — o `escrever()` a troca por "
        "um travessão solto no pé do cartão")


# --------------------------------------------------------------------------
# 6. o "?" também contava controle — e a régua dos cartões não o alcançava
# --------------------------------------------------------------------------
#: O trecho da página onde o "?" mora. A régua dos CARTÕES
#: (`test_nenhum_cartao_promete_um_numero_de_controles`) fatia a grade
#: `<div class="lancadores">`, e por construção o texto de ajuda fica FORA da
#: janela dela — foi por essa fresta que a última contagem de controle desta
#: aba sobreviveu à cura de 02/09/2026.
#:
#: E ELE É ANCORADO NO QUADRO DESTA ABA, não no primeiro `?` do arquivo —
#: medido ao morder a cura em 03/09/2026: com a `.dica` do quadro envenenada de
#: propósito, esta régua passou VERDE. O primeiro `<span class="ajuda">` da
#: página é o do **topo** (`topo.html:846`, o "?" do perfil ativo), que é das
#: DEZ abas e não tem número nenhum. *Seletor que casa o elemento errado dá
#: não-achado convincente* — e por isso a fatia começa no título do quadro.
_O_QUADRO = re.compile(
    r"De onde os seus jogos vêm.*?"
    r'<span class="ajuda">(?P<dica>.*?)</span></span>', re.S)


def _dica_da_pagina() -> str:
    achado = _O_QUADRO.search(_bancada())
    assert achado, (
        'a régua não achou o `?` do quadro "De onde os seus jogos vêm" — '
        "seletor que casa ZERO é erro, não silêncio")
    return achado.group("dica")


def test_o_texto_de_ajuda_nao_conta_controle_por_conta_propria():
    """Nenhum número solto no "?": quem conta a mesa tem de ter ENDEREÇO.

    O QUE ESTA RÉGUA MEDE, e por que ela não repete a dos cartões: a fatia é o
    `<span class="ajuda">`, e o que ela cobra é que todo DÍGITO ali dentro
    esteja dentro de um `data-campo` — quer dizer, que o produto possa
    reescrevê-lo no tique. Um número fora de endereço é o número do DESENHO,
    congelado no HTML pelo `monta.CONECTADOS` do gerador.

    MEDIDO NA JANELA DELA EM 03/09/2026, com um DualSense no cabo, antes da
    cura:

        cabeçalho   ``● 1 controle: 1 USB · 0 BT``   (lido do aparelho)
        o "?"       ``…vale igual para os 2 (1 no cabo, 1 no rádio)…``

    A MORDIDA: tire o `<span data-campo="lanc-quantos">` do `aba07.py`, regere
    a bancada, e este teste nomeia os dígitos que sobraram nus.
    """
    dica = _dica_da_pagina()
    # Fora os trechos ENDEREÇADOS — esses o produto reescreve a cada tique.
    nus = re.sub(r'<span data-campo="[^"]+"[^>]*>.*?</span>', " ", dica,
                 flags=re.S)
    # E FORA AS MARCAS: o que a régua mede é o que ela LÊ na tela. Um `22px`
    # de `style=` não está na tela e contá-lo faria a régua reprovar o CSS —
    # que é a forma de régua que esta casa mais paga (*a régua reprovando o
    # que não é o defeito*).
    texto = re.sub(r"<[^>]+>", " ", nus)
    sobrou = sorted({" ".join(t.split())
                     for t in re.findall(r"[^.;!?]*\d[^.;!?]*", texto)})
    assert not sobrou, (
        f"o texto de ajuda tem número que o produto não reescreve: {sobrou}. "
        f"Ele vem do `monta.CONECTADOS`, a mesa do DESENHO, e fica na tela "
        f"dela ao lado de um cabeçalho que lê o aparelho.")


def test_o_quantos_do_ajuda_sai_da_mesa_viva_e_nao_do_mockup(a07, desenho):
    """Mesas diferentes, frases diferentes — e a do mockup não é privilegiada.

    UMA CONSTANTE PASSARIA no teste de cima (ela também não tem dígito nu, se
    alguém a puser dentro do span). O que a desmascara é VARIAR a mesa: o valor
    emitido tem de mudar com ela, e tem de fechar com o que o cabeçalho diz.
    """
    import pacotes

    def frase(mesa):
        contexto = pacotes.Contexto(state={"active_profile": "regua"},
                                    mesa=mesa, conectados=[], estados={})
        return a07.pacote(contexto)[desenho.QUANTOS]

    # A MESA VIVA TRAZ `transporte`, E A CONTA LÊ ELE — ONDA4-S10, 06/09/2026.
    # Estas mesas de mentira tinham só `via`, a palavra que a TELA escreve, e a
    # conta somava por ela: bastava a palavra mudar (a decisão D-05 dela) para a
    # frase do "?" dizer *"0 no cabo, 2 no rádio"* com os dois no cabo — calado.
    # `mesa_viva.mesa_do_estado` publica as duas chaves lado a lado; a de
    # mentira aqui passa a ter as duas também, senão ela mede uma mesa que o
    # produto não produz.
    um_no_cabo = [{"pref": "p1", "jogador": 1, "via": "USB", "transporte": "usb"}]
    dois = [{"pref": "p1", "jogador": 1, "via": "USB", "transporte": "usb"},
            {"pref": "p2", "jogador": 2, "via": "BT", "transporte": "bt"}]

    assert frase(um_no_cabo) == "o <b>1</b> (1 no cabo, 0 no rádio)", (
        f"com UM controle no cabo o '?' diz {frase(um_no_cabo)!r} — e o "
        f"cabeçalho, na mesma tela, diz '1 controle: 1 USB · 0 BT'")
    assert frase(dois) == "os <b>2</b> (1 no cabo, 1 no rádio)"
    assert frase(um_no_cabo) != frase(dois), (
        "a frase não mudou com a mesa — ela é constante, e uma constante aqui "
        "é a mesa do mockup com outro nome")
    # A CONTA FECHA SEMPRE: cabo + rádio = o total que a frase anuncia.
    for mesa in (um_no_cabo, dois, []):
        n, usb, bt = (int(x) for x in re.findall(r"\d+", frase(mesa)))
        assert usb + bt == n == len(mesa), (
            f"a frase não fecha para {len(mesa)} controle(s): {frase(mesa)!r}")


# --------------------------------------------------------------------------
# 12. AS QUATRO QUE ELA PEDIU EM 08/09/2026, olhando a aba com os quatro
#     DualSense na mesa
#
# AS RÉGUAS DAQUI MEDEM A PÁGINA **PUBLICADA**, e não a bancada, e a escolha é
# de alcance: a bancada é o que o gerador acabou de escrever, então uma régua
# sobre ela prova que o GERADOR funciona. O que estas precisam provar é que a
# mudança chegou ao arquivo que o `WebKit2.WebView` renderiza — publicar é um
# segundo ato, e um trabalho que morre entre os dois é trabalho que ninguém vê.
# --------------------------------------------------------------------------
#: ONDE A ABA ACABA E A ANOTAÇÃO COMEÇA. O `topo.html` chama a `.nota` de
#: *"legenda do mockup (fora da janela)"*, e é isso que ela é: prosa sobre a
#: aba, escrita para quem lê o desenho, não texto que a aba mostra.
_FIM_DA_ABA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"


def _publicada(com_a_legenda: bool = False) -> str:
    """A página que o PRODUTO renderiza — `interface/paginas/`.

    **SEM A LEGENDA POR PADRÃO**, e isso é cura de uma medição errada que esta
    régua fez de si mesma na estreia: a `.nota` do fim da página é ANOTAÇÃO — ela
    fala *sobre* a aba, e por isso cita as palavras da aba (`NÃO CHEGAM` já
    aparece três vezes lá, desde 02/09). Uma régua que procure uma palavra de
    tela no documento inteiro acha a prosa que a descreve e conclui que a tela a
    diz. É a **ARMADILHA DA PROSA** desta casa, na forma de régua: o texto que
    NARRA o padrão vira a primeira ocorrência dele.
    """
    caminho = (RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
               / "paginas" / PAGINA)  # noqa-acento: nome de PASTA, e caminho não leva acento
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    doc = caminho.read_text(encoding="utf-8")
    if com_a_legenda:
        return doc
    if _FIM_DA_ABA not in doc:
        pytest.fail(
            f"a marca da legenda sumiu de {PAGINA}: sem ela esta régua mediria "
            f"a anotação junto com a aba, e a prosa que descreve uma palavra de "
            f"tela viraria a primeira ocorrência dela")
    return doc.split(_FIM_DA_ABA, 1)[0]


def test_o_selo_do_nao_localizado_e_a_palavra_dela(desenho):
    """A PALAVRA É DELA, e este é o ÚNICO lugar que a digita.

    08/09/2026, olhando a aba: *"ao invés de não achei. Deveria ter Não
    Localizado"*.

    **POR QUE UMA RÉGUA PODE DIGITAR AQUI, e as outras não:** esta é a régua
    DONA da decisão — o lugar onde a palavra dela fica registrada, para que
    trocá-la exija passar por ela. Toda régua que apenas PRECISA do selo lê
    `SELOS["off"]`; se elas também digitassem, a próxima palavra dela reprovaria
    dez réguas por estar certa, que é o defeito que esta casa nomeou onze vezes
    em 26/08.

    A MORDIDA: volte `SELOS["off"]` a qualquer outra coisa e esta linha reprova.
    """
    assert desenho.SELOS["off"] == "NÃO LOCALIZADO", (
        f"o selo do estado 'procurei e não achei' diz "
        f"{desenho.SELOS['off']!r}, e a palavra dela é 'NÃO LOCALIZADO'")


def test_a_palavra_do_selo_chega_a_pagina_publicada(desenho):
    """O selo é PINTADO, e por isso a cor dele tem de existir na folha publicada.

    O `data-hef-alvo="html"` do cartão troca o `<span class="lanc-selo off">`
    inteiro, então a palavra chega pelo produto — mas a CLASSE `off` tem de
    existir no CSS da página publicada, senão o selo novo nasce sem cor.

    A MORDIDA: tire `.lanc-selo.off` do CSS do `aba07.py`, regere e publique;
    esta régua reprova. E ela NÃO procura a palavra no HTML de propósito: o
    estado de partida é `nao_sei` nos seis cartões, e afirmar "não localizei"
    antes de procurar é o desenho fingindo ser produto.
    """
    doc = _publicada()
    assert ".lanc-selo.off" in doc, (
        "a classe do selo NÃO LOCALIZADO não existe no CSS publicado — o selo "
        "chega pintado pelo produto e nasce sem cor nenhuma")
    assert desenho.SELOS["off"] not in doc, (
        f"a página estática já diz {desenho.SELOS['off']!r} — ela nasce no "
        f"estado 'ainda não procurei', e afirmar 'não localizei' antes de "
        f"procurar é o desenho fingindo ser produto")


def test_nao_ha_cartao_da_epic_e_o_heroic_e_a_porta_das_duas_lojas(desenho):
    """A DECISÃO É DELA, E É A SEGUNDA — 08/09/2026, e ela desfaz a primeira.

    Ela pediu o cartão de manhã (*"Seria interessante termos o da Epic Games
    Aqui também não?"*), ele foi feito, e ela o viu e o tirou:
    *"melhor deixar só heróic e tirar epic games não?"*, *"Epic e gog ficam
    dentro do heróic. Melhor mesmo seu ponto"*.  # noqa-acento: grafia dela

    **A RÉGUA GUARDA AS DUAS METADES, e as duas são necessárias.** Só cobrar
    que o cartão não exista deixaria alguém tirar o «(Epic · GOG)» do rótulo do
    Heroic num dia de faxina — e aí a Epic sumiria da tela inteira, que é o
    contrário do que ela decidiu. Com o cartão fora, aquele rótulo é o ÚNICO
    lugar onde a Epic aparece, e ele passou a carregar a decisão.

    A MORDIDA TEM DUAS: acrescente um `SemCenso("epic", …)` ao `SEM_FONTE` e a
    primeira metade reprova; tire o «Epic» do rótulo do Heroic e a segunda
    reprova nomeando a loja que sumiu da tela.
    """
    chaves = [x.chave for x in desenho.EMBUTIDOS]
    assert "epic" not in chaves, (
        f"a Epic voltou a ter cartão: {chaves}. Ela decidiu o contrário depois "
        f"de ver o cartão pronto — e o argumento dela é medido: quem entrega o "
        f"jogo da Epic aqui é o Heroic, então os dois cartões procurariam o "
        f"MESMO programa em disco e o segundo só repetiria a resposta do "
        f"primeiro.")

    heroic = next(x for x in desenho.SEM_FONTE if x.chave == "heroic")
    for loja in ("Epic", "GOG"):
        assert loja in heroic.nome, (
            f"o rótulo do Heroic é {heroic.nome!r} e não nomeia a {loja}. Com o "
            f"cartão da Epic fora por decisão dela, este rótulo é o ÚNICO lugar "
            f"da tela onde aquela loja aparece — tirá-lo daqui apaga a loja da "
            f"interface inteira, que é o oposto do que ela pediu.")

    # E NENHUMA FRASE DE TELA FALA DE EPIC POR CONTA PRÓPRIA: as três frases dos
    # cartões são as gerais, e uma quarta redação só para uma loja voltaria a
    # ser um segundo dono do mesmo assunto.
    for frase in (desenho.DIZ_ACHEI, desenho.DIZ_NAO_ACHEI, desenho.DIZ_SEM_FONTE):
        assert "Epic" not in frase, (
            f"uma frase geral de cartão passou a nomear a Epic: {frase!r}. O "
            f"lugar da Epic é o rótulo do Heroic, e um segundo lugar envelhece "
            f"separado.")


def test_o_lancador_declarado_entra_no_cartao(desenho, a07, monkeypatch,
                                              tmp_path):
    """O QUE ELA ACRESCENTA VIRA CARTÃO, e passa pelo MESMO procurador.

    Pedido dela, 08/09/2026: *"Pensei em outro botão pra Adicionar novo Emulador
    Ou novo lançador algo assim, pra devs mais experimentais"*.

    A RÉGUA COBRE O CICLO INTEIRO — declarar, achar, desenhar, esquecer —
    porque é o ciclo que a tela dela faz. Provar só a gravação daria verde sobre
    um cartão que nunca aparece, que foi exatamente o defeito medido ao
    construir isto: um `NameError` engolido por um `except Exception` deixava o
    registro morto em SILÊNCIO, com o motor inteiro de pé.

    A MORDIDA TEM TRÊS: faça `_declarados()` devolver `()`; faça a busca
    percorrer `EMBUTIDOS` em vez de `procurados(...)`; ou faça o `None` deixar
    de apagar. As três reprovam aqui, cada uma numa linha diferente.
    """
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    pasta = _pastas_falsas(monkeypatch, tmp_path, "org.ryujinx.Ryujinx")
    assert gravar_maquina({"lancadores": {"ryujinx": {
        "rotulo": "Ryujinx", "atalhos": ["org.ryujinx.Ryujinx"]}}})

    declarados = a07._declarados()
    assert [x.chave for x in declarados] == ["ryujinx"], (
        f"o que ela declarou não voltou do disco: {declarados}. Sem isto o "
        f"cartão nunca aparece, e nada na tela diz por quê.")

    onde = dict(a07._onde_estao_os_lancadores(declarados))
    assert onde["ryujinx"] == str(pasta / "org.ryujinx.Ryujinx.desktop"), (
        f"o procurador não percorreu o declarado: {onde}. Um segundo caminho de "
        f"busca é a assimetria que esta casa passou o dia arrancando.")

    lida = desenho.Leitura(declarados=declarados, onde_estao=tuple(onde.items()))
    cartoes = {c.chave: c for c in desenho.cartoes(lida)}
    assert "ryujinx" in cartoes, f"o declarado não virou cartão: {sorted(cartoes)}"
    assert cartoes["ryujinx"].nome == "Ryujinx" and cartoes["ryujinx"].presente
    assert desenho.REMOVER_ROTULO in desenho.acoes_html(cartoes["ryujinx"]), (
        "o cartão declarado não tem como sair — a lista dela vira lixo "
        "permanente, e a única saída seria editar o `maquina.json` à mão")

    # O DESFAZER: `None` apaga, e o disco não guarda lápide nenhuma.
    assert gravar_maquina({"lancadores": {"ryujinx": None}})
    assert a07._declarados() == (), (
        "o «Tirar daqui» não tirou. `machine.declare` funde dicionário com "
        "dicionário, e sem o `None` a chave sobrevive do lado do disco.")


def test_o_declarado_com_a_chave_de_um_de_fabrica_ensina_o_cartao(desenho):
    """CHAVE REPETIDA NÃO VIRA SEGUNDO CARTÃO — ela soma à busca do primeiro.

    É o sentido literal do «Adicionar Launcher» do cartão que não localizou:
    *"ele está aqui, eu te mostro onde"*. Dois cartões com a mesma chave seriam
    pior que inúteis — os endereços do desenho levam a chave como prefixo
    (`data-campo="retroarch-selo"`), e o piloto pintaria o valor de um nos DOIS.

    A MORDIDA: troque a fusão por um `append` em `procurados` e esta régua
    reprova nas duas primeiras linhas.
    """
    ensino = desenho.SemCenso("retroarch", "O Meu RetroArch",
                              ("meu-retroarch",), ("/opt/retro",),
                              declarado=True)
    lista = desenho.procurados((ensino,))
    chaves = [x.chave for x in lista]
    assert chaves.count("retroarch") == 1, (
        f"a chave repetida virou um segundo cartão: {chaves}. Os dois teriam o "
        f"MESMO `data-campo`, e o piloto pintaria o valor de um nos dois.")
    ra = next(x for x in lista if x.chave == "retroarch")
    assert "meu-retroarch" in ra.atalhos and "/opt/retro" in ra.comandos, (
        "o que ela ensinou não entrou na busca do cartão de fábrica")
    assert "org.libretro.RetroArch" in ra.atalhos, (
        "o ensino dela APAGOU a busca de fábrica — quem ensina soma, não troca")
    assert ra.nome == "RetroArch", (
        "o rótulo de fábrica foi trocado pelo dela: aquele nome é desenho que "
        "ela aprovou, e o que este botão acrescenta é ONDE procurar")
    assert ra.declarado, (
        "o cartão ensinado não sabe que foi ensinado, e por isso não oferece o "
        "«Tirar daqui» — o ensino ficaria sem desfazer")


def test_a_tela_de_registro_chega_a_pagina_publicada(desenho):
    """O botão global, a tela e os dois campos — no arquivo que o produto abre.

    A MORDIDA: tire a injeção da tela do `aba07.py`, regere e publique; esta
    régua reprova nomeando o `id` que sumiu. Ela cobra o `id` porque o botão
    aponta para ele: um `href="#novo-lancador"` para um `id` que não existe abre
    NADA, e o clique some sem uma palavra.
    """
    doc = _publicada()
    assert f'id="{desenho.TELA_DO_NOVO}"' in doc, (
        f"a tela de registro não está na página publicada. O botão aponta para "
        f"#{desenho.TELA_DO_NOVO}, e um `href` para um `id` que não existe abre "
        f"nada — o clique some sem uma palavra.")
    assert f'href="#{desenho.TELA_DO_NOVO}"' in doc, (
        "nada na página abre a tela de registro")
    assert f'data-gesto="{desenho.ADICIONAR}"' in doc, (
        "o «Adicionar» da tela não tem endereço — o clique não chega ao Python")
    assert f'data-hef-forma="{desenho.TELA_DO_NOVO}"' in doc, (
        "o «Adicionar» não pede a forma: o ouvinte do piloto manda o valor do "
        "elemento CLICADO, e o botão é outro elemento — sem isto ele chegaria "
        "ao Python sem uma letra do que ela digitou")
    for campo in (desenho.NOVO_ROTULO, desenho.NOVO_ALVO):
        assert f'data-linha="{campo}"' in doc, (
            f"o campo {campo!r} não está na tela publicada")
        assert f'data-campo="{campo}"' not in doc, (
            f"o campo {campo!r} ganhou `data-campo`: o piloto o repintaria dez "
            f"vezes por segundo por cima do que ela está digitando")
    assert f'data-campo="{desenho.NOVO_PARA_QUEM}"' in doc, (
        "a tela não diz PARA QUAL cartão ela abriu — quem chega pelo botão de "
        "um cartão vê dois campos vazios e nenhuma pista")


class _PonteQueAnota:
    """Guarda o que o gesto mandou pela ponte, e responde como o daemon."""

    def __init__(self) -> None:
        self.chamadas: list[dict] = []

    def machine_declare(self, maquina: dict) -> tuple[bool, None]:
        self.chamadas.append(maquina)
        return True, None


def test_o_registro_nao_grava_o_que_nao_esta_no_disco(a07, ctx, desenho):
    """GRAVAR UM LANÇADOR QUE NÃO ESTÁ LÁ É FABRICAR UM CARTÃO QUE MENTE.

    E ele mentiria para sempre: a busca nunca o acharia, e o cartão diria «NÃO
    LOCALIZADO» sobre uma coisa que ela mesma acabou de declarar.

    A MORDIDA: tire a chamada a `onde_isso_esta` do gesto e esta régua reprova —
    a ponte que anota registra a gravação que não devia ter acontecido.
    """
    p = _PonteQueAnota()
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    with pytest.raises(RuntimeError) as caiu:
        a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
            desenho.NOVO_ROTULO: "Fantasma",
            desenho.NOVO_ALVO: "isto-nao-existe-em-lugar-nenhum"}}, p)
    assert "Não achei" in str(caiu.value), (
        f"a recusa não diz que não achou: {caiu.value}")
    assert p.chamadas == [], (
        f"o gesto GRAVOU um lançador que não está no disco: {p.chamadas}")

    # E O QUE EXISTE GRAVA — senão esta régua daria verde com o gesto morto.
    r = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
        desenho.NOVO_ROTULO: "O Shell", desenho.NOVO_ALVO: "/bin/sh"}}, p)
    assert p.chamadas == [{"lancadores": {"o-shell": {
        "rotulo": "O Shell", "comandos": ["/bin/sh"]}}}], (
        f"o gesto não gravou o que ESTÁ no disco: {p.chamadas}")
    assert "/bin/sh" in r["recado"], (
        f"o recibo não diz ONDE — sem o caminho ela tem de acreditar em mim: "
        f"{r['recado']!r}")


def test_o_botao_do_cartao_diz_a_tela_para_qual_lancador(a07, ctx, desenho):
    """A PRIMEIRA METADE DO GESTO: apontar, sem gravar nada.

    Sem ela a tela abriria com dois campos vazios e nenhuma pista de para qual
    cartão — e a segunda metade teria de adivinhar pelo texto, que é o palpite
    que esta aba inteira existe para não dar.

    A MORDIDA: faça o ramo sem `forma` gravar, ou devolver antes de escrever o
    `NOVO_PARA_QUEM`, e esta régua reprova nas duas direções.
    """
    p = _PonteQueAnota()
    r = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR,
                                     "v": "retroarch"}, p)
    assert p.chamadas == [], "o clique que só ABRE a tela gravou alguma coisa"
    assert "RetroArch" in r["mesa"][desenho.NOVO_PARA_QUEM], (
        f"a tela não diz que abriu para o RetroArch: "
        f"{r['mesa'][desenho.NOVO_PARA_QUEM]!r}")

    vazio = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    assert vazio["mesa"][desenho.NOVO_PARA_QUEM] == desenho.NOVO_SEM_ALVO, (
        "o botão GLOBAL herdou o alvo do clique anterior — ela pediu um "
        "lançador novo e a tela diria o nome de um cartão que ela não escolheu")


def test_tirar_daqui_recusa_um_cartao_de_fabrica(a07, ctx, desenho):
    """Não há o que desfazer onde ela não declarou nada.

    A MORDIDA: deixe o gesto mandar o `None` sem conferir a lista dela e esta
    régua reprova — a ponte registra uma gravação sobre um cartão de fábrica.
    """
    p = _PonteQueAnota()
    with pytest.raises(RuntimeError):
        a07.esquecer_lancador(ctx, {"gesto": desenho.REMOVER, "v": "lutris"}, p)
    assert p.chamadas == [], (
        f"o gesto escreveu no `maquina.json` sobre um cartão de fábrica: "
        f"{p.chamadas}")
    with pytest.raises(ValueError):
        a07.esquecer_lancador(ctx, {"gesto": desenho.REMOVER, "v": ""}, p)


def test_o_schema_recusa_um_declarado_que_a_busca_nunca_acharia():
    """A SEGUNDA GUARDA, e ela alcança o que o gesto não alcança.

    O gesto da tela recusa antes de gravar, e recusa MAIS — ele confere que o
    que ela digitou EXISTE no disco agora. Esta é a de FORMA, e vale para o que
    não passa pelo gesto: um `maquina.json` escrito à mão, ou um gesto futuro.

    ELA NASCEU DE UMA MEDIÇÃO no dia em que o campo nasceu:
    `{"rotulo": "X", "comandos": ["", "  "]}` PASSAVA. O aparador de agulha
    vazia deixava a tupla vazia, o documento gravava, e a busca nunca acharia
    aquilo — um cartão «NÃO LOCALIZADO» permanente sobre uma coisa que ela mesma
    declarou. O cartão que mente, chegando pelo lado do disco.

    A MORDIDA: tire o `_sem_agulha_nao_ha_o_que_procurar` de
    `LancadorDeclarado` e a primeira metade desta régua reprova.
    """
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    for nome, decl in (
        ("sem agulha nenhuma", {"rotulo": "Fantasma"}),
        ("só agulha em branco", {"rotulo": "Fantasma", "comandos": ["", "  "]}),
        ("rótulo em branco", {"rotulo": "   ", "comandos": ["/bin/sh"]}),
    ):
        with pytest.raises(ValueError):
            gravar_maquina({"lancadores": {"fantasma": decl}})
        assert "fantasma" not in _lancadores_do_disco(), (
            f"o schema aceitou um lançador {nome}: a busca nunca o acharia, e o "
            f"cartão dele diria «não localizei» para sempre")

    # E A CHAVE TAMBÉM É FORMA: ela vira `data-lancador` e o prefixo de cada
    # `data-campo` do cartão. Uma com aspas quebraria a marcação da grade.
    for chave in ("Ryu Jinx", 'a"b', "MAIÚSCULA", "a" * 33, ""):
        with pytest.raises(ValueError):
            gravar_maquina({"lancadores": {chave: {"rotulo": "X",
                                                   "comandos": ["/bin/sh"]}}})

    # E O QUE VALE VALE — senão esta régua daria verde recusando tudo.
    assert gravar_maquina({"lancadores": {"ryujinx": {
        "rotulo": "Ryujinx", "comandos": ["/bin/sh"]}}})
    assert "ryujinx" in _lancadores_do_disco()


def _lancadores_do_disco() -> dict:
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return dict(carregar_maquina().lancadores)


def test_a_recusa_do_botao_global_manda_clicar_num_botao_que_existe(a07, ctx,
                                                                    desenho):
    """A TELA NÃO MANDA CLICAR ONDE NÃO HÁ NADA — e mandava, num cartão.

    O botão global recusa um nome que já tem cartão de fábrica, e a recusa
    manda usar o botão DAQUELE cartão. Enquanto o cartão da Steam não tinha o
    botão, essa frase fechava um beco: as duas únicas portas para dizer onde a
    Steam está eram o botão que não existia e o botão que apontava para ele.

    A RÉGUA COBRA OS DOIS LADOS AO MESMO TEMPO — o texto da recusa e a fileira
    do cartão que ela nomeia —, e é o único jeito de o beco não voltar: cada
    metade sozinha continuaria verde enquanto a outra some.

    A MORDIDA TEM DUAS: tire o `acao_de_localizar` do ramo `off` de
    `cartao_da_steam` e a segunda asserção reprova nomeando a Steam; troque o
    `desenho.ADICIONAR_ROTULO` da recusa por um texto digitado e a primeira
    reprova no dia em que o rótulo mudar.
    """
    lida = desenho.Leitura(
        onde_estao=tuple((x.chave, "") for x in desenho.EMBUTIDOS))
    fileiras = {c.chave: desenho.acoes_html(c) for c in desenho.cartoes(lida)}

    p = _PonteQueAnota()
    for item in desenho.EMBUTIDOS:
        # O QUE SE DIGITA É A CHAVE, e não o rótulo do cartão: quem decide a
        # colisão é `chave_do_rotulo`, e dois dos seis rótulos não derivam para
        # a própria chave ("Heroic (Epic · GOG)" vira `heroic-epic-gog`). Usar o
        # rótulo aqui faria a régua medir o caminho do cartão NOVO em dois dos
        # seis casos — e dar verde sobre o ramo que ela existe para cobrar.
        assert a07.chave_do_rotulo(item.chave) == item.chave, (
            f"a chave {item.chave!r} não sobrevive à derivação — a régua não "
            f"chegaria ao ramo da recusa")
        # O botão GLOBAL: `v` vazio, e o nome digitado cai sobre um de fábrica.
        a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
        with pytest.raises(RuntimeError) as caiu:
            a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
                desenho.NOVO_ROTULO: item.chave,
                desenho.NOVO_ALVO: "/bin/sh"}}, p)
        recusa = str(caiu.value)
        assert desenho.ADICIONAR_ROTULO in recusa, (
            f"a recusa do {item.chave!r} não nomeia o botão do cartão: "
            f"{recusa!r} — sem o nome, quem lê não sabe para onde ir")
        assert desenho.ADICIONAR_ROTULO in fileiras[item.chave], (
            f"a recusa manda usar «{desenho.ADICIONAR_ROTULO}» do cartão "
            f"{item.chave!r}, e AQUELE CARTÃO NÃO TEM ESSE BOTÃO. A fileira "
            f"dele é: {fileiras[item.chave]!r}. É um beco: as duas portas para "
            f"dizer onde este lançador está apontam uma para a outra.")
    assert p.chamadas == [], (
        f"a recusa gravou alguma coisa: {p.chamadas}")


def test_o_campo_que_esta_aba_criou_tem_rotulo_de_tela():
    """O `lancadores` do `maquina.json` NASCEU AQUI — e o rótulo dele é daqui.

    ESTA RÉGUA NASCEU DE UMA REGRESSÃO MEDIDA — 08/09/2026. O campo entrou no
    `MaquinaConfig` com o botão de registro e **não ganhou rótulo de tela** em
    `app/ipc_bridge.py`. Sem ele, `_rotulos_dos_descartados` cai no
    `rotulos.get(campo, campo)` e a barra de status dela mostra a palavra crua
    `lancadores` no dia em que o documento em disco trouxer o campo corrompido.

    **E OS PORTÕES FICARAM VERDES**: quem cobrava isso era
    `test_descartados_chegam_ao_rodape.py`, que não está no `portoes.sh` nem no
    `ci.yml`. A régua irmã continua sendo a autoritativa — ela cobre o schema
    INTEIRO, campo a campo, e reprova rótulo sobrando. Esta cobre o campo que a
    ABA criou, e mora aqui pela razão de sempre: quem acrescenta o campo paga o
    rótulo, e paga na régua que ele já roda.

    A MORDIDA: tire `"lancadores"` do `_ROTULOS_SEM_SECAO` e esta régua reprova.
    """
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    assert "lancadores" in MaquinaConfig.model_fields, (
        "o campo saiu do schema — a régua estaria medindo o vazio")
    rotulo = ipc_bridge._rotulos_dos_descartados({"descartados": ["lancadores"]})
    assert rotulo and rotulo[0] != "lancadores", (
        f"o campo que esta aba criou chega à barra de status dela como a "
        f"palavra CRUA do JSON: {rotulo!r}. O rótulo mora em "
        f"`ipc_bridge._ROTULOS_SEM_SECAO`.")
    assert "ançador" in rotulo[0], (
        f"o rótulo do `lancadores` é {rotulo[0]!r} e não nomeia o que se perde. "
        f"A frase do rodapé diz «isto o Hefesto não entendeu e descartou: …», e "
        f"quem lê precisa saber que perdeu onde os lançadores dela estão.")
