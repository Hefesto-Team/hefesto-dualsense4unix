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


def test_o_produto_procura_os_cinco_pelas_pastas_do_motor(a07, monkeypatch,
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
    assert set(onde) == {"heroic", "lutris", "flatpak", "retroarch",
                         "emuladores"}, (
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

    assert desenho.SELOS[nao_achei.selo] == "NÃO ACHEI"
    assert not nao_achei.presente and not nao_procurei.presente
    assert achei.presente, "um lançador achado não conta como encontrado no topo"
    assert len({nao_procurei.diz, nao_achei.diz, achei.diz}) == 3, (
        "dois dos três estados dizem a MESMA frase — a tela voltou a não "
        "separar 'procurei e não achei' de 'ainda não procurei'")
    assert "com.heroicgameslauncher.hgl.desktop" in achei.diz, (
        "o cartão diz que achou e não diz ONDE — sem isso ela não tem como "
        "conferir a resposta sem acreditar em mim")


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
    """
    item = next(x for x in desenho.SEM_FONTE if x.chave == "retroarch")
    vazio = desenho.acoes_html(desenho.cartao_sem_censo(item, ""))
    assert vazio, "a fileira vazia voltou a ser string vazia — a tela mostra `—`"
    assert "<button" not in vazio, "um botão apareceu num cartão sem o que abrir"
    assert desenho.valores_do_cartao(
        desenho.cartao_sem_censo(item, ""))["retroarch-acoes"] == vazio

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
# 7. as duas leituras do disco que tela NENHUMA mostrava
# --------------------------------------------------------------------------
def test_os_jogos_dispensados_do_lembrete_aparecem_na_lista(desenho):
    """O `launch_dialog_dismissed.json` ganha a primeira tela da casa.

    A escrita tinha dono (o botão "Não perguntar para este jogo" do lembrete da
    GTK) e a LEITURA não tinha nenhuma: clicar produzia um silêncio permanente
    que ninguém podia consultar depois.
    """
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           dispensados=(("4242", "Jogo Dispensado"),))
    fora = desenho.valores_do_cartao(
        desenho.cartao_da_steam(lida))["steam-fora"]
    assert "Jogo Dispensado" in fora and "não perguntar mais" in fora, (
        "o jogo dispensado não aparece na lista do cartão da Steam")
    assert 'data-v="4242"' not in fora, (
        "a linha do dispensado ganhou botão — e `launch_wrapper_dialog` não "
        "tem `remove_dismissed_appid`: o clique não teria o que chamar")


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
