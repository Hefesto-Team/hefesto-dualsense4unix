#!/usr/bin/env python3
"""A RÉGUA DA ABA LANÇADORES: o que ela AFIRMA tem de vir de uma medição."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"


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


_AS_DUAS_COPIAS = ("hefesto_dualsense4unix.interface.pacotes.a07_lancadores",
                   "pacotes.a07_lancadores")


@pytest.fixture(autouse=True)
def _a_vigia_so_le_quando_a_regua_pede(monkeypatch):
    """Nenhuma régua daqui acorda a thread da `VIGIA` por tabela."""
    import importlib

    for nome in _AS_DUAS_COPIAS:
        try:
            modulo = importlib.import_module(nome)
        except Exception:
            continue
        monkeypatch.setattr(modulo.VIGIA, "_disparar", lambda: None)


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"}, mesa=[],
                            conectados=[], estados={})


def _bancada() -> str:
    """A página da BANCADA — o desenho de HOJE, não o congelado."""
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    return caminho.read_text(encoding="utf-8")


def test_todo_endereco_da_pagina_tem_quem_o_pinte(a07, ctx):
    """Zero vazios e zero órfãos — nos DOIS sentidos."""
    fora = a07.pacote(ctx)
    da_grade = "".join(str(v) for v in (fora.get("blocos") or {}).values())
    da_pagina = set(CAMPO.findall(_bancada() + da_grade)) - _do_topo()
    emite = {k for k in fora
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
    """Um botão com endereço e sem quem o atenda some no clique."""
    import pacotes

    no_html = set(GESTO.findall(_bancada()))
    com_dono = {n for (p, n) in pacotes.GESTOS if p == PAGINA}
    assert no_html <= com_dono, (
        f"a página tem gestos que ninguém atende: {sorted(no_html - com_dono)}")
    assert com_dono - no_html <= {"consertar", "ver-o-que-impede",
                                  "tirar-daqui", "voltar-a-usar",
                                  "voltar-a-perguntar", "nao-perguntar",
                                  "consertar-fechando-a-steam",
                                  "copiar-a-linha",
                                  "desligar-steam-input",
                                  "deixar-tudo-pronto",
                                  "adicionar-a-exclusao",
                                  "confirmar-exclusao",
                                  "confirmar-perfil",
                                  "tirar-da-exclusao",
                                  "esquecer-lancador",
                                  "consertar-lancador"}, (
        f"estes gestos têm dono e não aparecem em estado nenhum da página: "
        f"{sorted(com_dono - no_html)}")


def test_os_botoes_que_a_pintura_traz_existem_no_html_pintado(a07, ctx, desenho):
    """A fileira pintada da Steam é a MESMA nos dois estados — e é a dos outros sete."""
    lida = desenho.Leitura(
        com_wrapper=("1",),
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),),
        instalados=3)
    html = desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-acoes"]
    ok = desenho.Leitura(com_wrapper=("1",), instalados=1)
    html_ok = desenho.Quadro(
        lancadores=desenho.cartoes(ok)).valores()["steam-acoes"]
    for acao in desenho.fileira_comum(desenho.STEAM):
        assert f'data-gesto="{acao.gesto}"' in html, (
            f"o cartão da Steam com jogo faltando perdeu o «{acao.rotulo}»")
    assert html == html_ok, (
        "a fileira da Steam com jogo faltando não é a do dia bom — um botão "
        "que só aparece num estado é um botão que os outros cartões não têm")
    for nome in ("consertar", "ver-o-que-impede"):
        assert f'data-gesto="{nome}"' not in html, (
            f"o botão {nome!r} voltou ao cartão da Steam")


def test_nenhum_lancador_sem_fonte_afirma_que_os_controles_chegam(desenho):
    """`CHEGAM`/`NÃO CHEGAM` só para quem o produto MEDE."""
    for item in desenho.SEM_FONTE:
        for onde in (None, "", f"{item.chave}.desktop"):
            cartao = desenho.cartao_sem_censo(item, onde)
            assert cartao.selo in ("nao_sei", "off", "localizado"), (
                f"o cartão {item.chave!r} com onde={onde!r} afirma "
                f"{desenho.SELOS[cartao.selo]!r} e o produto não lê a "
                f"biblioteca dele.")
        nascendo = next(c for c in desenho.cartoes(None) if c.chave == item.chave)
        assert nascendo.selo == "nao_sei" and not nascendo.presente, (
            f"o cartão {item.chave!r} afirma algo antes de a leitura voltar")


def test_os_cinco_lancadores_ganharam_leitor_de_biblioteca():
    """**ESTA RÉGUA VIROU DO AVESSO em 09/09/2026, e era o que ela pedia.**"""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    sem_leitor = [n for n in ("Heroic", "Lutris", "RetroArch", "Dolphin", "mGBA")
                  if not censo.sabe_ler(n)]

    assert sem_leitor == [], (
        f"estes lançadores perderam o leitor de biblioteca: {sem_leitor}. Sem "
        f"leitor o cartão volta a dizer `NÃO SEI` sobre um programa instalado, "
        f"que é o que ela chamou de «a aba lançadores tá identificando nada».")

    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as des

    mudos = [i.chave for i in des.SEM_FONTE
             if i.chave != "flatpak"
             and censo.biblioteca_do_cartao(i.chave).estado == censo.SEM_BIBLIOTECA]
    assert mudos == [], (
        f"estes cartões não sabem que lançador representam: {mudos} — o censo "
        f"existe e não chega neles")


def test_nenhum_cartao_promete_um_numero_de_controles(desenho):
    """A recaída da régua velha do gerador, cobrada também aqui."""
    grade = _bancada().split('<div class="lancadores">', 1)[-1].split("</div>\n\n")[0]
    assert 'data-lancador="steam"' in grade, (
        "a régua não achou a grade de cartões — seletor que casa ZERO é erro, "
        "não silêncio")
    tudo = desenho.cartoes_html(desenho.cartoes(None)) + grade
    assert not re.findall(r"[Oo]s \d+ controles chegam", tudo), (
        "um cartão voltou a prometer para um NÚMERO de controles")


def test_o_selo_segue_os_reparaveis_e_nao_os_faltantes(desenho):
    """Um jogo INTOCÁVEL não faz o cartão acusar impedimento."""
    so_intocavel = desenho.Leitura(
        com_wrapper=("1", "2"),
        intocaveis=(("9", "Jogo intocável", "linha editada à mão — não vou tocar"),),
        instalados=3)
    cartao = desenho.cartao_da_steam(so_intocavel)
    assert cartao.selo == "localizado", (
        "o cartão acusa impedimento por causa de um jogo que o produto não toca")
    assert "Jogo intocável" in cartao.fora and "à mão" in cartao.fora, (
        f"o jogo que o produto não toca sumiu da tela ({cartao.fora!r}) — "
        "ele fica sem o atalho para sempre e ninguém saberia")


def test_o_nome_do_jogo_e_escapado(desenho):
    """O rótulo vem do `appmanifest` DELA — é conteúdo de terceiro."""
    lida = desenho.Leitura(
        reparaveis=(("7", '<b>&"joguinho"', "nunca recebeu o atalho"),),
        instalados=1)
    html = desenho.lista_de_jogos(lida)
    assert "<b>&" not in html and "&lt;b&gt;" in html, (
        "um nome de jogo com marcação quebraria o cartão")


def test_a_pintura_nunca_grava_o_registro_de_wrapper_visto(a07, monkeypatch):
    """A MORDIDA PRINCIPAL: `anotar=False`, e ele não é zelo."""
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
    assert vistos, "ninguém chamou o censo — a régua mediria o vazio"
    assert set(vistos) == {False}, (
        f"a leitura da tela pediu `anotar={vistos}`. Com `True` ela GRAVA o "
        f"`wrapper-visto.json` a cada tique, e todo jogo novo vira 'já visto' "
        f"antes de ela ver o aviso uma única vez.")


def test_o_tique_nao_bloqueia_no_disco(a07, ctx, monkeypatch):
    """A pintura devolve o que tem — nunca espera o disco."""
    def _nunca(*a, **kw):
        raise AssertionError("a pintura leu o disco na thread da janela")

    monkeypatch.setattr(a07, "_ler_do_disco", _nunca)
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "_dado", None, raising=False)
    pacote = a07.pacote(ctx)
    assert pacote["steam-jogos"] == a07.desenho.AINDA_LENDO, (
        "sem leitura o cartão tem de dizer que ainda está lendo — um número "
        "que não foi lido é um número inventado")


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


def test_detectar_recusa_dizendo_quando_nao_ha_jogo(ctx, monkeypatch):
    """Sem jogo aberto o botão RECUSA — não inventa um jogo nem responde calado."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(slo, "steam_game_running_appid", lambda: None)
    with pytest.raises(RuntimeError, match="jogo"):
        _gesto("detectar")(ctx, {}, None)


def test_esta_regua_nao_alcanca_a_biblioteca_dela():
    """A pergunta que custou dez minutos em 02/09, respondida por medição."""
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    real = str(pathlib.Path.home())
    for caminho in (sw.caminho_do_registro(), slo.sem_wrapper_path()):
        assert not str(caminho).startswith(real + "/.local"), (
            f"a régua escreveria em {caminho}, que é o estado DELA")
    assert slo.discover_vdfs() == [], (
        "a régua enxerga um `localconfig.vdf` de verdade — o isolamento do "
        "`conftest` caiu, e um teste desta aba passaria a ler a biblioteca dela")


def test_o_piso_de_gestos_da_aba_so_sobe(a07):
    """Ele SÓ SOBE por queda sem querer. Uma queda não aparece na tela: o clique"""
    import pacotes

    quantos = sum(1 for (p, _) in pacotes.GESTOS if p == PAGINA)
    assert quantos >= a07.PISO_DA_ABA == 14, (
        f"{PAGINA} tem {quantos} gestos com dono e o piso é {a07.PISO_DA_ABA}")


def _pastas_falsas(monkeypatch, tmp_path, *stems: str):
    """Uma pasta de `.desktop` de mentira, com os atalhos que o teste quiser."""
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
    assert onde["lutris"] == str(pasta / "net.lutris.Lutris.desktop"), (
        f"o produto não achou o atalho que está em disco, ou jogou fora o "
        f"caminho que torna a resposta conferível: {onde}")
    assert onde["heroic"] == "", (
        "o produto disse ter achado um lançador que não está na pasta")
    assert set(onde) == {x.chave for x in desenho.EMBUTIDOS}, (
        "a busca pulou um lançador — o cartão dele voltaria ao `NÃO SEI` de "
        "constante sem ninguém ver")

    assert dict(a07._ler_do_disco().onde_estao)["lutris"] == str(
        pasta / "net.lutris.Lutris.desktop"), (
        "a busca funciona e a LEITURA não a carrega — a tela volta ao `NÃO "
        "SEI` de constante com este teste verde")


def test_o_atalho_do_kde_nao_e_o_emulador(a07, monkeypatch, tmp_path):
    """`dolphin.desktop` é o gerenciador de arquivos do KDE, não o emulador."""
    _pastas_falsas(monkeypatch, tmp_path, "dolphin")
    assert dict(a07._onde_estao_os_lancadores())["emuladores"] == "", (
        "o `dolphin.desktop` do KDE passou por emulador")


def test_o_cartao_achado_e_o_nao_achado_dizem_coisas_diferentes(desenho):
    """Os três estados viram três telas — e o `NÃO ACHEI` deixa de ser letra morta."""
    item = next(x for x in desenho.SEM_FONTE if x.chave == "heroic")
    nao_procurei = desenho.cartao_sem_censo(item, None)
    nao_achei = desenho.cartao_sem_censo(item, "")
    achei = desenho.cartao_sem_censo(item, "com.heroicgameslauncher.hgl.desktop")

    assert nao_achei.selo == "off", (
        f"o estado 'procurei e não achei' deixou de produzir o selo `off` — ele "
        f"produz {nao_achei.selo!r}, e a palavra que a tela mostra é "
        f"{desenho.SELOS.get(nao_achei.selo)!r}")
    assert not nao_achei.presente and not nao_procurei.presente
    assert achei.presente, "um lançador achado não conta como encontrado no topo"
    assert len({nao_procurei.diz, nao_achei.diz, achei.diz}) == 3, (
        "dois dos três estados dizem a MESMA frase — a tela voltou a não "
        "separar 'procurei e não achei' de 'ainda não procurei'")
    # *"remove as frases do achei esse lançador aqui"*.  (noqa-acento) citação
    assert achei.diz == desenho.contador_html(0), (
        f"o cartão do lançador ACHADO diz outra coisa além do contador: "
        f"{achei.diz!r}. Ela o calou em 11/09 e deu a ele o contador em 21/09")
    assert nao_achei.diz and nao_procurei.diz, (
        "o cartão calado tinha de ser SÓ o do achado — os outros dois estados "
        "precisam da frase, porque neles o selo sozinho não diz o que fazer")


def test_todo_cartao_tem_botao_nos_tres_estados_e_o_do_ausente_e_outro(desenho):
    """OS SEIS CARTÕES, e o nome desta régua já foi «os cinco»."""
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
            elif estado == "ainda não procurei":
                for rotulo in (desenho.ADICIONAR_ROTULO,
                               desenho.APONTAR_ROTULO):
                    assert rotulo not in html, (
                        f"o cartão {cartao.chave!r} em {estado!r} oferece "
                        f"«{rotulo}» antes de o produto ter procurado — e isso "
                        f"muda a página publicada")
            else:
                assert desenho.APONTAR_ROTULO in html, (
                    f"o cartão {cartao.chave!r} em {estado!r} (selo "
                    f"{cartao.selo!r}) não oferece "
                    f"«{desenho.APONTAR_ROTULO}» — se o que o Hefesto achou "
                    f"não é o que ela quer, não há por onde trocar, e a recusa "
                    f"do botão global volta a mandar clicar no vazio")
                assert desenho.ADICIONAR_ROTULO not in html, (
                    f"o cartão {cartao.chave!r} em {estado!r} diz "
                    f"{cartao.selo!r} no selo e «{desenho.ADICIONAR_ROTULO}» "
                    f"no botão — lidos de cima para baixo, os dois se "
                    f"contradizem")

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
    """A PALAVRA É DELA — 08/09/2026: *"Adicionar novo Lançador? Seria legal um"""
    do_cartao = desenho.ADICIONAR_ROTULO
    global_ = desenho.ADICIONAR_NOVO_ROTULO
    assert do_cartao != global_, (
        f"os dois botões voltaram a dizer a mesma coisa ({do_cartao!r}): um é "
        f"«ele está aqui, te mostro onde» e o outro é «tem um que você não "
        f"conhece». Ela pediu um sinônimo justamente para separá-los.")
    # aprovou: *"ok aprovadíssimo todas. Manda ver."*  # noqa-acento: citação dela
    assert do_cartao == "Localizar este lançador", (
        f"o rótulo do botão do cartão é {do_cartao!r}, e a decisão dela é "
        f"'Localizar este lançador' — a palavra do SELO daquele cartão")
    assert global_ == desenho.TELA_DO_NOVO_TITULO, (
        f"o botão global diz {global_!r} e a tela que ele abre se chama "
        f"{desenho.TELA_DO_NOVO_TITULO!r}. Decisão dela de 11/09/2026: um nome "
        f"por tela — quem clica tem de chegar onde o botão prometeu")
    assert desenho.APONTAR_ROTULO == "Outro caminho", (
        f"o rótulo do cartão LOCALIZADO é {desenho.APONTAR_ROTULO!r}, e a "
        f"decisão dela é 'Outro caminho' (21/09/2026)")
    assert desenho.APONTAR_DICA == "Apontar outro caminho para este lançador"
    assert len({do_cartao, global_, desenho.APONTAR_ROTULO}) == 3, (
        "dois dos três rótulos de registro voltaram a dizer a mesma coisa — "
        "cada um responde por um estado diferente do cartão")

    for rotulo in (do_cartao, global_, desenho.TELA_DO_NOVO_TITULO,
                   desenho.REMOVER_ROTULO):
        assert "launcher" not in rotulo.lower(), (
            f"{rotulo!r} voltou ao inglês. A tela desta casa fala português.")

    assert "LOCALIZ" in desenho.SELOS["off"].upper(), (
        f"o selo do estado ausente é {desenho.SELOS['off']!r} e o botão dele diz "
        f"{do_cartao!r} — os dois deixaram de falar a mesma palavra, que era a "
        f"razão de o sinônimo ter esta forma e não outra")


def test_o_titulo_da_tela_de_registro_nao_contradiz_o_botao_que_a_abriu(desenho):
    """A CAIXA É UMA E OS CAMINHOS SÃO DOIS — e o título não pode ser de um só."""
    titulo = desenho.TELA_DO_NOVO_TITULO
    assert "novo" not in titulo.lower(), (
        f"o título da caixa é {titulo!r}. A caixa é UMA e chega-se a ela por "
        f"dois caminhos: aberta pelo botão de um cartão que JÁ existe, um "
        f"título com «novo» contradiz a linha logo abaixo, que diz o nome "
        f"daquele cartão.")
    assert titulo != desenho.ADICIONAR_ROTULO, (
        f"o título da caixa é o rótulo do botão do CARTÃO ({titulo!r}) — o "
        f"caminho em que ele é aberto sobre um cartão existente. Metade das "
        f"aberturas mostraria um título que não é o do botão que as abriu.")
    assert titulo in desenho.tela_do_registro_html(), (
        "o título não chegou à marcação da tela de registro")

    do_cartao = desenho.tela_do_registro_html(
        desenho.NOVO_PARA_O_CARTAO.format(nome="RetroArch"))
    assert "RetroArch" in do_cartao, (
        "a tela aberta pelo botão de um cartão não diz de qual cartão")
    assert desenho.NOVO_SEM_ALVO in desenho.tela_do_registro_html(), (
        "a tela aberta pelo botão global perdeu a linha que diz o que ela é")

    for nome in ("Steam", "RetroArch", "Dolphin · mGBA"):
        linha = desenho.NOVO_PARA_O_CARTAO.format(nome=nome)
        assert not linha.lower().startswith(("o ", "a ")), linha
        assert f" o {nome}" not in linha and f" a {nome}" not in linha, (
            f"a linha voltou a pôr artigo antes do nome do cartão: {linha!r}. "
            f"Os nomes têm gêneros diferentes e um deles vem do teclado dela — "
            f"adivinhar o artigo é palpite na tela.")


def test_a_contagem_do_topo_conta_presenca_e_nao_selo(desenho):
    """`N localizados` responde "quantos estão aqui", não "em quantos eu sei"."""
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("heroic", "h.desktop"), ("lutris", "")))
    quadro = desenho.Quadro(lancadores=desenho.cartoes(lida))
    assert quadro.achados == 2, (
        f"a Steam e o Heroic estão aqui e a conta diz {quadro.achados}")
    assert desenho.conta_html(quadro.achados, quadro.impedidos).startswith(
        desenho._plural(2, "localizado", "localizados"))


def test_nenhuma_fileira_de_botoes_vira_travessao(desenho):
    """Fileira vazia não pode virar `—` na tela. Fotografado em 02/09/2026."""
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
    """A borda do cartão e o selo dentro dele não podem discordar."""
    assert f'class="{desenho.CLASSE_DA_GRADE}"' in _bancada(), (
        f"a página não tem a grade `{desenho.SELETOR_DA_GRADE}` — o `blocos` "
        f"cairia no chão, e `querySelector` devolve `null` sem uma linha de erro")

    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    carga = a07.pacote(ctx)
    grade = (carga.get("blocos") or {}).get(desenho.SELETOR_DA_GRADE)
    assert grade, (
        "o pacote não manda a grade — a classe do contêiner fica a do desenho "
        "para sempre, e o cartão se pinta como outra coisa do que mede")

    lida = desenho.Leitura(com_wrapper=("1", "2"), instalados=23,
                           reparaveis=(),
                           onde_estao=(("heroic", ""), ("lutris", "")))
    cartoes = desenho.cartoes(lida)
    html = a07._pintura(cartoes)["blocos"][desenho.SELETOR_DA_GRADE]
    assert cartoes[0].selo == "localizado", (
        "a Leitura da régua deixou de ser a do cartão sem impedimento")
    assert f'class="lanc {desenho.MOLDURA["localizado"]}" data-lancador="steam"' in html, (
        "a Steam mede `LOCALIZADO` e a moldura dela continua a de `ausente` — é "
        "o cartão dizendo duas coisas opostas na mesma tela")

    quebrada = desenho.cartoes(desenho.Leitura(
        com_wrapper=("1",), instalados=2,
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),)))
    html_warn = a07._pintura(quebrada)["blocos"][desenho.SELETOR_DA_GRADE]
    assert f'class="lanc {desenho.MOLDURA["warn"]}" data-lancador="steam"' in (
        html_warn), (
        "a Steam mede `NÃO CHEGAM` e a borda não fica laranja — a única coisa "
        "que esta aba mostra sem ler é a cor")


def test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa(a07, desenho):
    """As duas grafias do mesmo valor têm de ser UMA — senão a tela pinga-pongue."""
    lida = desenho.Leitura(
        com_wrapper=("1",), instalados=3,
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),),
        recusados=(("9", "Outro jogo"),),
        onde_estao=(("heroic", "/x/h.desktop"), ("lutris", "")))
    cartoes = desenho.cartoes(lida)
    grade = a07._pintura(cartoes)["blocos"][desenho.SELETOR_DA_GRADE]
    valores = desenho.Quadro(lancadores=cartoes).valores()

    for chave, valor in valores.items():
        if chave == "lanc-conta":
            continue
        assert f">{valor}<" in grade, (
            f"o campo {chave!r} é pintado com uma grafia e a grade traz outra. "
            f"As duas se corrigem a cada tique, para sempre — foi assim que o "
            f"piloto contou pintura em 81 de 81 voltas.")


_VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
           "meta", "source", "track", "wbr"}


def _como_o_dom_devolve(marcacao: str) -> str:
    """Reserializa a marcação pelas regras que o WEBKIT DELA usa. É medida."""
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


_NOMES_QUE_MORDEM = ("Assassin's Creed", 'O jogo "bom"', "Ratchet & Clank",
                     "a < b > c", "espa\u00e7o\u00a0duro", "Tom Clancy's")


@pytest.mark.parametrize("nome", _NOMES_QUE_MORDEM)
def test_a_marcacao_volta_igual_do_dom(a07, desenho, nome):
    """Um apóstrofo no nome de UM jogo reescrevia a GRADE INTEIRA, para sempre."""
    lida = desenho.Leitura(
        com_wrapper=("1",), instalados=3,
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
    """A régua acima só vale se ela souber reprovar. Aqui está a prova."""
    assert _como_o_dom_devolve("<b>a&#x27;b</b>") == "<b>a'b</b>"
    assert _como_o_dom_devolve("<b>a&quot;b</b>") == '<b>a"b</b>'
    assert _como_o_dom_devolve('<b x="a&#x27;b"></b>') == '<b x="a\'b"></b>'
    assert _como_o_dom_devolve('<b x="a&quot;b"></b>') == '<b x="a&quot;b"></b>'
    assert _como_o_dom_devolve("<b>a\u00a0b</b>") == "<b>a&nbsp;b</b>"
    assert _como_o_dom_devolve("<b>a&amp;b</b>") == "<b>a&amp;b</b>"
    assert _como_o_dom_devolve('<b x="a&lt;b"></b>') == '<b x="a&lt;b"></b>'
    assert _como_o_dom_devolve("<!-- nada -->") == "<!-- nada -->"


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
    _gesto("voltar-a-perguntar")


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
    with pytest.raises(RuntimeError, match="lembrete continua desligado"):
        _gesto("voltar-a-perguntar")(ctx, {"v": "4242"}, None)


def test_a_ponte_confirmada_chega_ao_contador(desenho):
    """`◆ N jogos já sabem por onde entrar` — a promessa que estava sem fonte."""
    sem = desenho.Leitura(com_wrapper=("1",), instalados=1)
    assert desenho.cartao_da_steam(sem).diz == desenho.contador_html(0)

    com = desenho.Leitura(com_wrapper=("1",), instalados=1, pontes=3)
    diz = desenho.cartao_da_steam(com).diz
    assert "3 jogos já sabem por onde entrar" in diz, (
        f"a ponte confirmada sumiu do corpo do cartão da Steam: {diz!r}")
    assert desenho.cartao_da_steam(com).carimbo == "", (
        "o contador foi para o carimbo — o lugar dele é o corpo, como nos "
        "outros sete")


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

    valores = a07._valores(lida)
    assert "3 jogos já sabem por onde entrar" in valores["steam-diz"] + (
        valores["steam-acoes"]), (
        "as pontes chegaram à leitura e não chegaram ao carimbo do cartão")
    assert "Jogo 4242" in valores["steam-fora"], (
        "o jogo dispensado chegou à leitura e não chegou à lista do cartão")


def test_a_contagem_do_topo_nao_cai_depois_do_gesto(a07, monkeypatch, desenho):
    """`_com_outra_frase` não pode devolver um cartão com campo perdido."""
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("heroic", "h.desktop"), ("lutris", "")))
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: lida)

    do_tique = a07._valores(lida)["lanc-conta"]
    do_gesto = a07._com_outra_frase("uma frase qualquer")["mesa"]["lanc-conta"]

    assert desenho._plural(2, "localizado", "localizados") in do_tique, (
        f"a régua perdeu o pé: a pintura do tique já não conta 2 ({do_tique!r})")
    assert do_gesto == do_tique, (
        f"a contagem do topo MUDA depois do gesto — o tique diz {do_tique!r} e "
        f"o gesto devolve {do_gesto!r}. A tela discorda de si mesma sem que "
        f"nenhum cartão tenha mudado.")

    assert a07._com_outra_frase("outra")["mesa"]["steam-fora"], (
        "o cartão trocado perdeu a lista de jogos")


def test_a_steam_quebrada_nao_apaga_a_resposta_sobre_os_outros(a07, monkeypatch,
                                                               tmp_path):
    """Duas perguntas independentes não podem cair juntas."""
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


def test_a_steam_ausente_nao_afirma_que_os_controles_chegam(a07, desenho,
                                                            monkeypatch,
                                                            tmp_path):
    """O CAMINHO INTEIRO: busca vazia → leitura → cartão → conta do topo."""
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    _pastas_falsas(monkeypatch, tmp_path)

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
    assert desenho._plural(0, "localizado", "localizados") in \
        a07._valores(lida)["lanc-conta"], (
            "a conta chegou certa ao quadro e errada à tela")


def test_a_steam_sem_procura_e_sem_biblioteca_nao_conta_como_encontrada(desenho):
    """O CONTRATO do `presente`, e esta régua nasceu de uma mordida que FALHOU."""
    cartao = desenho.cartao_da_steam(desenho.Leitura())
    assert not cartao.presente, (
        "o `presente` do cartão da Steam voltou a ser constante: uma leitura "
        "que não procurou nada e não leu nada conta como lançador encontrado")


def test_a_steam_que_esta_aqui_continua_respondendo_pelo_censo(a07, desenho,
                                                               monkeypatch,
                                                               tmp_path):
    """A MESA DELA não pode mudar: achada, o cartão volta a ser o de sempre."""
    _pastas_falsas(monkeypatch, tmp_path, "steam")
    lida = desenho.Leitura(
        com_wrapper=("1", "2"), instalados=2,
        onde_estao=tuple(a07._onde_estao_os_lancadores()))
    cartao = desenho.cartao_da_steam(lida)
    assert cartao.selo == "localizado" and cartao.presente, (
        f"a Steam ACHADA e com a biblioteca lida perdeu o cartão de sempre: "
        f"selo {cartao.selo!r} ({desenho.SELOS[cartao.selo]!r}), "
        f"presente={cartao.presente}")
    assert "2 jogos instalados" in cartao.jogos


def test_a_steam_fora_das_tres_buscas_nao_apaga_a_biblioteca_lida(desenho):
    """As DUAS perguntas discordando: não achei o lançador, mas li a biblioteca."""
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1,
                           onde_estao=(("steam", ""),))
    cartao = desenho.cartao_da_steam(lida)
    assert cartao.selo == "localizado", (
        f"o produto leu 1 jogo da biblioteca e o cartão sai com selo "
        f"{cartao.selo!r} ({desenho.SELOS[cartao.selo]!r}) — a tela discorda "
        f"de si mesma")
    assert cartao.presente, (
        "a biblioteca foi lida e o topo não conta a Steam como encontrada")

    quebrada = desenho.Leitura(erros=("o vdf sumiu",), onde_estao=(("steam", ""),))
    diz = desenho.cartao_da_steam(quebrada).diz
    assert desenho.DIZ_NAO_LI in diz and desenho.DIZ_NAO_ACHEI not in diz, (
        f"um vdf ilegível virou 'não achei este lançador': {diz!r}")


def test_o_cartao_da_steam_nao_achada_mantem_os_enderecos_da_pagina(desenho):
    """O estado novo não pode tirar um endereço da página publicada."""
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
    nus = re.sub(r'<span data-campo="[^"]+"[^>]*>.*?</span>', " ", dica,
                 flags=re.S)
    texto = re.sub(r"<[^>]+>", " ", nus)
    sobrou = sorted({" ".join(t.split())
                     for t in re.findall(r"[^.;!?]*\d[^.;!?]*", texto)})
    assert not sobrou, (
        f"o texto de ajuda tem número que o produto não reescreve: {sobrou}. "
        f"Ele vem do `monta.CONECTADOS`, a mesa do DESENHO, e fica na tela "
        f"dela ao lado de um cabeçalho que lê o aparelho.")


#     DualSense na mesa
_FIM_DA_ABA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"


def _publicada(com_a_legenda: bool = False) -> str:
    """A página que o PRODUTO renderiza — `interface/paginas/`."""
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
    """A PALAVRA É DELA, e este é o ÚNICO lugar que a digita."""
    assert desenho.SELOS["off"] == "NÃO LOCALIZADO", (
        f"o selo do estado 'procurei e não achei' diz "
        f"{desenho.SELOS['off']!r}, e a palavra dela é 'NÃO LOCALIZADO'")


def test_a_palavra_do_selo_chega_a_pagina_publicada(desenho):
    """O selo é PINTADO, e por isso a cor dele tem de existir na folha publicada."""
    doc = _publicada()
    assert ".lanc-selo.off" in doc, (
        "a classe do selo NÃO LOCALIZADO não existe no CSS publicado — o selo "
        "chega pintado pelo produto e nasce sem cor nenhuma")
    assert desenho.SELOS["off"] not in doc, (
        f"a página estática já diz {desenho.SELOS['off']!r} — ela nasce no "
        f"estado 'ainda não procurei', e afirmar 'não localizei' antes de "
        f"procurar é o desenho fingindo ser produto")


def test_nao_ha_cartao_da_epic_e_o_heroic_e_a_porta_das_duas_lojas(desenho):
    """A DECISÃO É DELA, E É A SEGUNDA — 08/09/2026, e ela desfaz a primeira."""
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

    for frase in (desenho.DIZ_NAO_ACHEI, desenho.DIZ_SEM_FONTE):
        assert "Epic" not in frase, (
            f"uma frase geral de cartão passou a nomear a Epic: {frase!r}. O "
            f"lugar da Epic é o rótulo do Heroic, e um segundo lugar envelhece "
            f"separado.")


def test_o_lancador_declarado_entra_no_cartao(desenho, a07, monkeypatch,
                                              tmp_path):
    """O QUE ELA ACRESCENTA VIRA CARTÃO, e passa pelo MESMO procurador."""
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

    assert gravar_maquina({"lancadores": {"ryujinx": None}})
    assert a07._declarados() == (), (
        "o «Tirar daqui» não tirou. `machine.declare` funde dicionário com "
        "dicionário, e sem o `None` a chave sobrevive do lado do disco.")


def test_o_declarado_com_a_chave_de_um_de_fabrica_ensina_o_cartao(desenho):
    """CHAVE REPETIDA NÃO VIRA SEGUNDO CARTÃO — ela soma à busca do primeiro."""
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
    """O botão global, a tela e os dois campos — no arquivo que o produto abre."""
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
    """GRAVAR UM LANÇADOR QUE NÃO ESTÁ LÁ É FABRICAR UM CARTÃO QUE MENTE."""
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

    r = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
        desenho.NOVO_ROTULO: "O Shell", desenho.NOVO_ALVO: "/bin/sh"}}, p)
    assert p.chamadas == [{"lancadores": {"o-shell": {
        "rotulo": "O Shell", "comandos": ["/bin/sh"]}}}], (
        f"o gesto não gravou o que ESTÁ no disco: {p.chamadas}")
    assert "/bin/sh" in r["recado"], (
        f"o recibo não diz ONDE — sem o caminho ela tem de acreditar em mim: "
        f"{r['recado']!r}")


def test_o_botao_do_cartao_diz_a_tela_para_qual_lancador(a07, ctx, desenho):
    """A PRIMEIRA METADE DO GESTO: apontar, sem gravar nada."""
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
    """Não há o que desfazer onde ela não declarou nada."""
    p = _PonteQueAnota()
    with pytest.raises(RuntimeError):
        a07.esquecer_lancador(ctx, {"gesto": desenho.REMOVER, "v": "lutris"}, p)
    assert p.chamadas == [], (
        f"o gesto escreveu no `maquina.json` sobre um cartão de fábrica: "
        f"{p.chamadas}")
    with pytest.raises(ValueError):
        a07.esquecer_lancador(ctx, {"gesto": desenho.REMOVER, "v": ""}, p)


def test_o_schema_recusa_um_declarado_que_a_busca_nunca_acharia():
    """A SEGUNDA GUARDA, e ela alcança o que o gesto não alcança."""
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

    for chave in ("Ryu Jinx", 'a"b', "MAIÚSCULA", "a" * 33, ""):
        with pytest.raises(ValueError):
            gravar_maquina({"lancadores": {chave: {"rotulo": "X",
                                                   "comandos": ["/bin/sh"]}}})

    assert gravar_maquina({"lancadores": {"ryujinx": {
        "rotulo": "Ryujinx", "comandos": ["/bin/sh"]}}})
    assert "ryujinx" in _lancadores_do_disco()


def _lancadores_do_disco() -> dict:
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return dict(carregar_maquina().lancadores)


def test_a_recusa_do_botao_global_manda_clicar_num_botao_que_existe(
        a07, ctx, desenho, monkeypatch):
    """A TELA NÃO MANDA CLICAR ONDE NÃO HÁ NADA — e mandava, num cartão."""
    lida = desenho.Leitura(
        onde_estao=tuple((x.chave, "") for x in desenho.EMBUTIDOS))
    cartoes = {c.chave: c for c in desenho.cartoes(lida)}
    fileiras = {k: desenho.acoes_html(c) for k, c in cartoes.items()}

    monkeypatch.setattr(
        a07, "_botoes_do_cartao_agora",
        lambda chave: tuple(a.rotulo for a in cartoes[chave].acoes))

    p = _PonteQueAnota()
    for item in desenho.EMBUTIDOS:
        assert a07.chave_do_rotulo(item.chave) == item.chave, (
            f"a chave {item.chave!r} não sobrevive à derivação — a régua não "
            f"chegaria ao ramo da recusa")
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


def test_a_recusa_serve_os_tres_estados_do_cartao(a07, desenho):
    """A frase cita um botão QUE ESTÁ NA FILEIRA — nos três estados, não em um."""
    localizar = desenho.ADICIONAR_ROTULO
    tirar = desenho.acao_de_tirar(desenho.STEAM).rotulo
    achou = ("Abrir o lançador", "Criar perfil para um jogo")

    casos = (
        ("não achou", (localizar, tirar), localizar),
        ("achou, e ela apontou", (*achou, localizar, tirar), localizar),
        ("achou sozinho", (*achou, localizar), localizar),
        ("só ela apontou", (*achou, tirar), tirar),
        ("ainda não procurei", achou, None),
    )
    for estado, fileira, esperado in casos:
        frase = a07._recusa_de_quem_ja_tem_cartao(desenho.STEAM, "Steam", fileira)
        assert "Steam já tem cartão nesta aba" in frase, (estado, frase)
        citados = [r for r in (localizar, tirar) if r in frase]
        if esperado is None:
            assert not citados, (
                f"estado {estado!r}: a fileira é {fileira} e a recusa manda "
                f"clicar em {citados} — nenhum deles está lá. A tela não manda "
                f"clicar onde não há nada; sem botão, ela diz o fato e para.")
            continue
        assert citados == [esperado], (
            f"estado {estado!r}: a fileira é {fileira} e a recusa cita "
            f"{citados}, não «{esperado}»")
        assert esperado in fileira, (
            f"estado {estado!r}: a recusa manda usar «{esperado}» e AQUELE "
            f"CARTÃO NÃO TEM ESSE BOTÃO — é o beco de volta.")


def test_a_recusa_viva_nunca_cita_botao_ausente(a07, ctx, desenho):
    """O caminho de VERDADE, na máquina de verdade — sem `Leitura` montada."""
    p = _PonteQueAnota()
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    with pytest.raises(RuntimeError) as caiu:
        a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
            desenho.NOVO_ROTULO: desenho.STEAM,
            desenho.NOVO_ALVO: "/bin/sh"}}, p)

    frase = str(caiu.value)
    fileira = a07._botoes_do_cartao_agora(desenho.STEAM)
    for rotulo in (desenho.ADICIONAR_ROTULO,
                   desenho.acao_de_tirar(desenho.STEAM).rotulo):
        if rotulo in frase:
            assert rotulo in fileira, (
                f"a recusa viva manda clicar em «{rotulo}» e a fileira do "
                f"cartão da Steam nesta máquina é {fileira} — é o beco.")


def test_o_tirar_daqui_alcanca_os_seis_cartoes(desenho):
    """*O que se acrescenta se tira* — e o sexto cartão não tinha régua nenhuma."""
    tirar = desenho.acao_de_tirar("x").rotulo

    def fileira(chave: str, declarado: bool) -> tuple[str, ...]:
        lida = desenho.Leitura(
            onde_estao=tuple((x.chave, "") for x in desenho.EMBUTIDOS),
            declarados=((desenho.SemCenso(chave=chave, nome=chave,
                                          declarado=True),)
                        if declarado else ()))
        c = next(x for x in desenho.cartoes(lida) if x.chave == chave)
        return tuple(a.rotulo for a in c.acoes)

    sem_desensinar = [x.chave for x in desenho.EMBUTIDOS
                      if tirar not in fileira(x.chave, True)]
    assert not sem_desensinar, (
        f"{sem_desensinar} tem declaração dela e NÃO oferece «{tirar}». O que "
        f"ela ensinou fica gravado para sempre — e o caminho errado junto.")

    fingem = [x.chave for x in desenho.EMBUTIDOS
              if tirar in fileira(x.chave, False)]
    assert not fingem, (
        f"{fingem} oferece «{tirar}» sem ela ter declarado nada. Um botão que "
        f"não tem o que desfazer é um botão que finge — a mesma regra que tirou "
        f"o «Tirar daqui» dos cinco cartões não ensinados.")


def test_o_nome_descartado_e_dito(a07, ctx, desenho, monkeypatch):
    """A tela não come em silêncio o que ela digitou."""
    p = _PonteQueAnota()
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": desenho.STEAM}, p)
    fora = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
        desenho.NOVO_ROTULO: "A MINHA STEAM DE TESTE",
        desenho.NOVO_ALVO: "/bin/sh"}}, p)

    recado = str((fora or {}).get("recado") or "")
    assert "A MINHA STEAM DE TESTE" in recado, (
        f"ela digitou um nome, o produto gravou outro e não disse: {recado!r}. "
        f"Um campo que a tela oferece e o produto descarta é um campo que finge.")
    assert "Steam" in recado, (
        f"o recado não diz com que nome o cartão ficou: {recado!r}")


def test_o_nome_igual_nao_vira_recado(a07, ctx, desenho):
    """E o aviso só sai quando há o que avisar — senão vira ruído em todo clique."""
    p = _PonteQueAnota()
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": desenho.STEAM}, p)
    fora = a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "forma": {
        desenho.NOVO_ROTULO: "steam", desenho.NOVO_ALVO: "/bin/sh"}}, p)

    recado = str((fora or {}).get("recado") or "")
    assert "não entrou" not in recado, (
        f"ela digitou o mesmo nome do cartão e a tela avisou de um descarte que "
        f"não houve: {recado!r}")


_SELOS_QUE_DIZEM_QUE_ESTA_BOM = ("ok", "localizado")


def test_cartao_que_nao_declara_defeito_nao_oferece_conserto(desenho):
    """A RÉGUA QUE NÃO EXISTIA — e é a que ELA fez em 09/09/2026, olhando a tela."""
    de_fabrica = [x.chave for x in desenho.EMBUTIDOS]
    onde = tuple((k, f"/usr/bin/{k}") for k in de_fabrica)
    estados = {
        "achei, e nada falta": desenho.Leitura(
            com_wrapper=("1",), instalados=1, onde_estao=onde),
        "achei, e há jogo sem o atalho": desenho.Leitura(
            com_wrapper=("1",), instalados=1, onde_estao=onde,
            reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),)),
        "ainda não procurei": None,
        "procurei e não achei": desenho.Leitura(
            onde_estao=tuple((k, "") for k in de_fabrica)),
    }

    acusados = []
    for estado, lida in estados.items():
        for cartao in desenho.cartoes(lida):
            if cartao.selo not in _SELOS_QUE_DIZEM_QUE_ESTA_BOM:
                continue
            for acao in cartao.acoes:
                if acao.rotulo.startswith("Consertar"):
                    acusados.append(
                        f"{cartao.chave} em {estado!r}: selo {cartao.selo!r} "
                        f"({desenho.SELOS.get(cartao.selo)!r}, moldura "
                        f"{desenho.MOLDURA.get(cartao.selo)!r}) e o botão "
                        f"«{acao.rotulo}»")

    assert not acusados, (
        "cartão que NÃO declara defeito nenhum oferecendo conserto:\n  "
        + "\n  ".join(acusados)
        + "\n\nO selo diz que está tudo bem, a moldura diz que está tudo bem, e "
          "embaixo disso o produto oferece consertar. Uma cura oferecida onde a "
          "tela não declarou defeito nenhum lê-se como cura de coisa nenhuma — "
          "é a palavra dela, de 09/09/2026.")


def test_a_steam_com_jogo_sem_o_atalho_continua_declarando_o_defeito(desenho):
    """A GUARDA DE VACUIDADE da régua acima, e da saída dos botões."""
    lida = desenho.Leitura(
        com_wrapper=("1",), instalados=3,
        reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),))
    steam = next(c for c in desenho.cartoes(lida) if c.chave == desenho.STEAM)

    assert steam.selo == "warn", (
        f"a Steam com jogo reparável deixou de sair `warn`: {steam.selo!r}")
    assert "1 jogo sem o atalho" in steam.diz, (
        f"o corpo parou de dizer quantos jogos estão sem o atalho: {steam.diz!r}")
    assert steam.diz.startswith(desenho.contador_html(0)), (
        "o contador deixou de abrir o corpo no estado do reparo")


class _Seletor:
    """O dublê de `ponte.escolher_arquivo` — e ele SABE RECUSAR."""

    def __init__(self, escolha) -> None:
        self.escolha = escolha
        self.pedidos: list[tuple[str, str, str]] = []
        self.chamadas: list[dict] = []

    def escolher_arquivo(self, titulo, padrao="*", **extra):
        self.pedidos.append((titulo, padrao, str(extra.get("sugestao") or "")))
        return self.escolha

    def machine_declare(self, maquina: dict) -> tuple[bool, None]:
        self.chamadas.append(maquina)
        return True, None


def _com_lar_de_mentira(monkeypatch, tmp_path):
    """`HOME` e as quatro pastas XDG dentro do `tmp` — o disco desta régua."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local/share"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "usr/share"))
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    pasta = tmp_path / ".local/share/applications"
    pasta.mkdir(parents=True, exist_ok=True)
    (tmp_path / "usr/share/applications").mkdir(parents=True, exist_ok=True)
    return pasta


def test_o_seletor_grava_o_desktop_que_ela_apontou(a07, ctx, desenho,
                                                   tmp_path, monkeypatch):
    """«Escolher o arquivo…» — decisão dela de 09/09/2026, a opção (C).

        "Ou no Máximo Localizar o lançador. aí eu mesmo
         abro a tela e procuro o .desktop."

    O QUE ESTA RÉGUA PROVA, e é o caminho inteiro: o gesto abre o seletor com o
    filtro e a pasta de partida, resolve o que voltou nas MESMAS buscas do
    procurador, e grava pela MESMA porta do «Adicionar» (`machine_declare`).

    **A MORDIDA:** troque `_achar_o_que_ela_apontou` por uma função que devolve
    o caminho cru sem procurar, e o `agulha` gravado deixa de ser o `stem` do
    atalho — o cartão passa a apontar para uma agulha que a busca nunca casa.
    """
    pasta = _com_lar_de_mentira(monkeypatch, tmp_path)
    atalho = pasta / "org.ryujinx.Ryujinx.desktop"
    atalho.write_text("[Desktop Entry]\nName=Ryujinx\n", encoding="utf-8")

    p = _Seletor(str(atalho))
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    fora = a07.procurar_o_arquivo(ctx, {"gesto": desenho.PROCURAR_O_ARQUIVO,
                                        "forma": {desenho.NOVO_ROTULO: "Ryujinx",
                                                  desenho.NOVO_ALVO: ""}}, p)

    assert p.pedidos, "o gesto não chegou a abrir o seletor do sistema"
    _titulo, padrao, sugestao = p.pedidos[0]
    assert padrao == "*.desktop", (
        f"o seletor abriu sem filtro de `.desktop`: {padrao!r} — ela pediu para "
        f"apontar o atalho, não para caçá-lo entre todos os arquivos do disco")
    assert sugestao == str(pasta), (
        f"o seletor abriu em {sugestao!r} e não na pasta de atalhos {str(pasta)!r} "
        f"— duas das quatro pastas dela ficam dentro de `~/.local`, que um "
        f"seletor aberto no `$HOME` com ocultos desligados NÃO mostra")
    assert p.chamadas == [{"lancadores": {
        "ryujinx": {"rotulo": "Ryujinx",
                    "atalhos": ["org.ryujinx.Ryujinx"]}}}], (
        f"o gesto não gravou a agulha que a busca casa: {p.chamadas}")
    assert str(atalho) in fora["recado"], (
        f"o recibo não diz ONDE — sem o caminho, ela teria de acreditar em mim: "
        f"{fora['recado']!r}")


def test_o_seletor_recusa_o_desktop_fora_das_pastas_em_que_o_produto_procura(
        a07, ctx, desenho, tmp_path, monkeypatch):
    """Um atalho que a busca nunca acharia viraria um cartão que mente PARA SEMPRE."""
    _com_lar_de_mentira(monkeypatch, tmp_path)
    solto = tmp_path / "Downloads" / "ryujinx.desktop"
    solto.parent.mkdir(parents=True, exist_ok=True)
    solto.write_text("[Desktop Entry]\nName=Ryujinx\n", encoding="utf-8")

    p = _Seletor(str(solto))
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    with pytest.raises(RuntimeError) as caiu:
        a07.procurar_o_arquivo(ctx, {"gesto": desenho.PROCURAR_O_ARQUIVO,
                                     "forma": {desenho.NOVO_ROTULO: "Ryujinx"}}, p)

    frase = str(caiu.value)
    assert "fora das pastas" in frase, (
        f"a recusa não diz o que está errado — a PASTA: {frase!r}")
    assert "Confira o caminho" not in frase, (
        f"a recusa mandou conferir um caminho que ela APONTOU com o mouse: "
        f"{frase!r}")
    assert p.chamadas == [], (
        f"o produto GRAVOU um lançador que a busca dele nunca acharia: "
        f"{p.chamadas}")


def test_cancelar_o_seletor_nao_e_erro_nem_noticia(a07, ctx, desenho,
                                                   tmp_path, monkeypatch):
    """Ela fechou o diálogo. Nada mudou, e a tela NÃO FALA."""
    _com_lar_de_mentira(monkeypatch, tmp_path)
    p = _Seletor(None)
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)

    assert a07.procurar_o_arquivo(
        ctx, {"gesto": desenho.PROCURAR_O_ARQUIVO, "forma": {}}, p) is None
    assert p.chamadas == [], f"cancelar GRAVOU alguma coisa: {p.chamadas}"


def test_o_seletor_aceita_um_programa_do_path(a07, ctx, desenho,
                                              tmp_path, monkeypatch):
    """O quarto caso medido: ela apontou um BINÁRIO, e não um atalho."""
    _com_lar_de_mentira(monkeypatch, tmp_path)
    binario = tmp_path / "opt" / "Ryujinx"
    binario.parent.mkdir(parents=True, exist_ok=True)
    binario.write_text("#!/bin/sh\n", encoding="utf-8")
    binario.chmod(0o755)

    p = _Seletor(str(binario))
    a07.adicionar_lancador(ctx, {"gesto": desenho.ADICIONAR, "v": ""}, p)
    a07.procurar_o_arquivo(ctx, {"gesto": desenho.PROCURAR_O_ARQUIVO,
                                 "forma": {desenho.NOVO_ROTULO: "Ryujinx"}}, p)

    assert p.chamadas == [{"lancadores": {
        "ryujinx": {"rotulo": "Ryujinx", "comandos": [str(binario)]}}}], (
        f"o binário apontado não entrou pelo campo `comandos`: {p.chamadas}")


def test_o_seletor_declara_que_mexe_na_maquina_dela(a07, desenho):
    """Com `--oculta` não há diálogo, logo a prova de clique NÃO pode acioná-lo.

    `pacotes.perigosos()` é DERIVADO do `grava=` do próprio gesto — nunca
    digitado numa lista distante —, e é isso que o mantém um commit em dia. É a
    mesma porta do «Importar» do rodapé, e pela mesma razão.

    **A MORDIDA:** tire o `grava="machine_declare"` do decorador e esta régua
    reprova; a `--prova-gesto` passaria a clicar num botão que abre um diálogo
    do sistema (ou, com a janela oculta, a gravar no `maquina.json` dela).
    """
    import pacotes

    assert ("07-lancadores.html", desenho.PROCURAR_O_ARQUIVO) in pacotes.perigosos()


_CONFISSOES = ("não tem por onde", "ainda não sei fazer", "por enquanto não dá",
               "não está pronto", "ainda não implementei")


def test_a_recusa_do_registro_nunca_confessa_divida_nossa(a07, desenho):
    """A TELA NÃO CONTA À USUÁRIA UM BURACO NOSSO — decisão dela, 07/09/2026."""
    localizar = desenho.ADICIONAR_ROTULO
    tirar = desenho.acao_de_tirar(desenho.STEAM).rotulo
    achou = ("Abrir o lançador", "Criar perfil para um jogo")
    fileiras = {
        "não achou": (localizar, tirar),
        "achou sozinho": (*achou, localizar),
        "achou, e ela apontou": (*achou, localizar, tirar),
        "só ela apontou": (*achou, tirar),
        "ainda não procurei": achou,
        "a leitura levantou": (),
    }

    acusadas = []
    for estado, fileira in fileiras.items():
        frase = a07._recusa_de_quem_ja_tem_cartao(desenho.STEAM, "Steam", fileira)
        for confissao in _CONFISSOES:
            if confissao in frase.casefold():
                acusadas.append(f"{estado}: …{confissao}… → {frase!r}")

    assert not acusadas, (
        "a recusa confessa dívida NOSSA na tela dela:\n  " + "\n  ".join(acusadas)
        + "\n\nDecisão dela, 07/09/2026: a dívida vai para o mapa "
          "(`docs/data/paridade-gtk-html.csv`), nunca para a tela. Ou o buraco "
          "fecha, ou ele fica no mapa — a tela não o conta.")


_REGRA_DE_SELO = re.compile(r"(?P<seletores>[^{}]+)\{(?P<corpo>[^{}]*)\}")


def _folha_da_aba() -> str:
    """O `<style>` da página da bancada, com a prosa decepada."""
    return re.sub(r"/\*.*?\*/", " ", _bancada(), flags=re.S)


def _corpo_da_regra_do_selo(folha: str, chave: str) -> str | None:
    """A declaração que pinta `.lanc-selo.<chave>`, ou `None` se não há nenhuma."""
    agulha = f".lanc-selo.{chave}"
    for regra in _REGRA_DE_SELO.finditer(folha):
        seletores = [s.strip() for s in regra.group("seletores").split(",")]
        if agulha in seletores:
            return " ".join(regra.group("corpo").split())
    return None


def test_todo_selo_do_produto_tem_cor_na_folha(desenho):
    """Um selo que o Python emite e a folha não conhece sai SEM PÍLULA."""
    folha = _folha_da_aba()
    sem_cor = [k for k in desenho.SELOS
               if _corpo_da_regra_do_selo(folha, k) is None]

    assert not sem_cor, (
        f"o produto emite {sorted(sem_cor)} e a folha da aba não pinta "
        f"nenhum deles: `<span class=\"lanc-selo {sem_cor[0]}\">` cai só na "
        f"`.lanc-selo` base, que dá tamanho e fonte e NÃO dá fundo — o selo "
        f"sai como texto solto ao lado do nome do cartão, e foi exatamente "
        f"isso que ela viu em 11/09/2026. `SELOS` e a folha são duas listas, "
        f"e quem acrescenta uma chave numa tem de acrescentar na outra.")


def test_os_selos_de_uma_mesma_moldura_tem_a_mesma_cor(desenho):
    """A família do selo já está escrita em `MOLDURA` — a folha a obedece."""
    folha = _folha_da_aba()
    familias: dict[str, list[str]] = {}
    for chave in desenho.SELOS:
        familias.setdefault(desenho.MOLDURA[chave], []).append(chave)

    discordantes = []
    for moldura, chaves in sorted(familias.items()):
        if len(chaves) < 2:
            continue
        pintados = {k: _corpo_da_regra_do_selo(folha, k) for k in sorted(chaves)}
        if len(set(pintados.values())) > 1:
            discordantes.append(f"moldura {moldura!r}: " + " · ".join(
                f"{k} → {v!r}" for k, v in pintados.items()))

    assert not discordantes, (
        "selos da MESMA moldura estão pintados de cores diferentes:\n  "
        + "\n  ".join(discordantes)
        + "\n\n`MOLDURA` é quem declara a família, e ela já dá a mesma moldura "
          "aos dois. Duas cores para o mesmo estado é uma cor a mais para ela "
          "decodificar — é a razão escrita em `MOLDURA` e a que `off`/`nao_sei` "
          "já cumprem.")


def test_a_lista_vazia_da_steam_nao_ocupa_um_pixel(desenho):
    """*"isso na steam essa frase tem que sumir pra nivelarmos a altura do bloco
    da styeam com demais."* — ela, 22/09/2026.

    A lista vazia era a frase «Nada pendente, e você não tirou nem dispensou
    nenhum jogo.» embaixo de uma linha, e só o cartão da Steam pagava os 28 px.
    Agora ela é SÓ um comentário HTML: o navegador não desenha nada, e o
    `:empty` da `.lanc-fora` ignora comentário — a borda e a margem somem
    junto. Um espaço em volta do comentário já quebraria o `:empty`.

    A MORDIDA: devolva a frase a `desenho_dos_lancadores.LISTA_VAZIA` e a
    primeira asserção reprova.
    """
    import re

    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    fora = desenho.valores_do_cartao(desenho.cartao_da_steam(lida))["steam-fora"]
    assert re.fullmatch(r"<!--.*?-->", fora, re.S), (
        f"a lista vazia da Steam voltou a desenhar alguma coisa: {fora!r}")
