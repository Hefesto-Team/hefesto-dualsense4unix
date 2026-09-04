#!/usr/bin/env python3
"""A RÉGUA DA ABA SISTEMA: onde o pacote cala, quem fala é o MOCKUP.

POR QUE ELA EXISTE, e é o defeito medido em 02/09/2026 com a janela aberta e o
daemon vivo: o `pacote()` desta aba DELEGA para `gui/aba_sistema.pacote`, que
sabe responder os doze endereços da página. Só que o `Leitura` que o alimentava
preenchia **três dos sete campos**. Os outros quatro chegavam `None`, a camada
do produto devolvia o traço honesto — e o traço nunca chegava à tela, porque o
pacote não emitia aqueles endereços.

**Uma página que não é pintada não fica em branco: ela fica com o desenho.** O
que a janela mostrava, contra o que a máquina dela respondia:

    Como ele enxerga a janela: —   Sem ver nada agora (sem_foco_x)
    O que ele impõe:          —    Nada é limitado
    Perfil ativo:             —    meu_perfil
    8 linhas · nenhum aviso        6 linhas · nenhum aviso
    "Steam Input estava ligado     Steam Input desligado para o DualSense
     em 2 jogos — desliguei"       (e mais cinco, nenhuma igual às do desenho)
    [23:41:02] daemon pronto …     não há registro nenhum sendo lido

AS QUATRO COISAS QUE ELA COBRA, e cada uma é um jeito diferente de recair:

1. **O `Leitura` chega COMPLETO.** Um campo que volta a ficar `None` por
   esquecimento é silencioso — nada levanta, e a tela volta a mostrar o desenho.
2. **O pacote emite endereço DA PÁGINA, e não nome de camada.** Foi por aqui que
   a chave `perfil` (o rótulo do perfil de BATERIA) apagou o `perfil` do
   cabeçalho — o perfil de JOGO, que é das dez abas.
3. **O exame vem do DADO.** A contagem e a lista saem do `storm_report`, com o
   `<span class="sep">` do desenho preservado.
4. **O painel de registro não pisca.** O que um gesto "Ver …" escreve fica; a
   pintura do tique seguinte repete o mesmo texto em vez de apagá-lo.

AS MORDIDAS estão no docstring de cada teste, e todas foram executadas.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O `state_full` de mentira — o suficiente para a camada do produto responder
#: cada uma das seis linhas sem inventar nada. O MAC é da faixa sintética da
#: casa: há dois portões de anonimato nesta árvore.
ESTADO = {
    "active_profile": "meu_perfil",
    "paused": False,
    "rumble_policy": "balanceado",
    "window_detect_backend": "xlib",
    "window_detect_seeing": False,
    "window_detect_reason": "sem_foco_x",
    "controllers": [
        {"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "usb"},
        {"uniq": "aa:bb:cc:00:00:02", "connected": True, "transport": "bt"},
    ],
}


@pytest.fixture
def a09():
    from pacotes import a09_sistema as mod

    # O PERFIL DE BATERIA É GRAVADO NO DISCO DE MENTIRA, e não injetado: o
    # `conftest.py` desta casa desvia `HOME` e os quatro `XDG_*` para um lar
    # que nasce sem `maquina.json`, e `perfil_na_tela()` responde `None` — que
    # é a verdade daquele lar, não um defeito. Gravando pelo caminho do PRODUTO
    # (`gravar_maquina`), a régua atravessa o mesmo disco que a mão dela
    # atravessa. Um `monkeypatch` em `perfil_na_tela` mediria o dublê.
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        PERFIL_BATERIA_LONGA,
        TETO_POR_PERFIL,
    )
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    gravar_maquina({"orcamento": {"teto": TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]}})

    # O CACHE DA FAIXA LENTA É ESVAZIADO A CADA TESTE, e é por isso que ele é um
    # `dict` de módulo e não um `lru_cache`: um cache que a régua não zera daria
    # verde sobre a leitura do teste ANTERIOR.
    mod._LENTO.clear()
    mod._PAINEL[0] = None
    yield mod
    mod._LENTO.clear()
    mod._PAINEL[0] = None


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(
        state=ESTADO, mesa=[],
        conectados=[c for c in ESTADO["controllers"]], estados={})


# ---------------------------------------------------------------------------
# 1. O `Leitura` chega COMPLETO
# ---------------------------------------------------------------------------
def test_a_leitura_preenche_os_sete_campos(a09, ctx):
    """Nenhum campo do `Leitura` pode voltar a chegar vazio por esquecimento.

    **A MORDIDA:** apague `ambiente=…` da chamada em `_leitura` e este teste
    reprova nomeando o campo. Executada em 02/09/2026:

        AssertionError: `Leitura.ambiente` chegou vazio à camada do produto.
        Com ele `None`, a linha que ele alimenta devolve o traço — e o traço
        não chega à tela: o que fica à vista é o literal do mockup.
    """
    leitura = a09._leitura(ctx)
    for campo in ("status", "autostart", "state", "achados", "deteccao",
                  "ambiente", "perfil"):
        assert getattr(leitura, campo) is not None, (
            f"`Leitura.{campo}` chegou vazio à camada do produto. Com ele "
            f"`None`, a linha que ele alimenta devolve o traço — e o traço não "
            f"chega à tela: o que fica à vista é o literal do mockup.")


def test_as_seis_linhas_deixam_de_ser_o_travessao(a09, ctx):
    """As seis linhas de estado respondem com DADO, não com `—`.

    É o teste que mede o efeito de 1 do lado de fora: um `Leitura` completo tem
    de virar seis valores escritos, e não seis traços honestos.

    **A MORDIDA:** troque `perfil=perfil_da_bateria` por `perfil=None` em
    `_leitura` e este teste reprova em `bateria-impoe`. Executada:

        AssertionError: `bateria-impoe` continua no traço — o pacote está
        emitindo o endereço e a fonte dele não foi lida.
    """
    p = a09.pacote(ctx)
    for endereco in ("hefesto-estado", "hefesto-pausa", "hefesto-troca-de-perfil",
                     "hefesto-ambiente", "bateria-impoe", "bateria-vale-para"):
        assert endereco in p, f"o pacote parou de emitir `{endereco}`"
        assert p[endereco] != "—", (
            f"`{endereco}` continua no traço — o pacote está emitindo o "
            f"endereço e a fonte dele não foi lida.")


def test_a_faixa_lenta_nao_repete_o_subprocesso_a_cada_tique(a09, ctx):
    """`systemctl`, `storm_report` e o disco: UMA vez a cada `LENTO_S`.

    O tique da pintura é de 500 ms. Sem a faixa lenta, três leituras caras
    rodariam duas vezes por segundo para escrever o que não muda entre dois
    piscares — e o `systemctl` JÁ rodava assim antes desta mudança.

    **A MORDIDA:** troque o `if _LENTO and …` de `_faixa_lenta` por `if False:`
    e este teste reprova com `2 != 1`.
    """
    chamadas = []
    original = a09._autostart
    a09._autostart = lambda: (chamadas.append(1), "enabled")[1]
    try:
        a09._leitura(ctx)
        a09._leitura(ctx)
        a09._leitura(ctx)
    finally:
        a09._autostart = original
    assert len(chamadas) == 1, (
        f"a faixa lenta leu {len(chamadas)} vezes em três tiques — ela existe "
        f"para ler UMA vez a cada {a09.LENTO_S}s.")


# ---------------------------------------------------------------------------
# 2. O pacote emite endereço DA PÁGINA
# ---------------------------------------------------------------------------
def _campos_da_pagina() -> set[str]:
    """Os `data-campo` da página PUBLICADA — lidos, nunca digitados."""
    import onde

    doc = onde.pagina("09-sistema.html", publicado=True).read_text(encoding="utf-8")
    return set(re.findall(r'data-campo="([^"]+)"', doc))


def test_o_pacote_nao_apaga_o_perfil_do_cabecalho(a09, ctx):
    """`perfil` é do CABEÇALHO das dez abas. Este pacote não pode emiti-lo.

    O ESTRAGO MEDIDO, fotografado em 02/09/2026 às 04:23: este pacote emitia
    `perfil` com o rótulo do PERFIL DE BATERIA — que ninguém lia, logo `None`.
    `pacotes.topo()` pinta o perfil de JOGO com `setdefault`, então chegava
    tarde: o cabeçalho da aba Sistema dizia `Perfil ativo —` com o daemon
    publicando `active_profile: 'meu_perfil'`.

    **A MORDIDA:** volte a linha `fora["perfil"] = bruto.get("perfil")` ao
    `pacote()` e este teste reprova. Executada:

        AssertionError: o pacote da 09 voltou a emitir `perfil`, que é o
        endereço do CABEÇALHO (o perfil de JOGO, dono `pacotes.topo`).
    """
    import pacotes

    p = a09.pacote(ctx)
    assert "perfil" not in p, (
        "o pacote da 09 voltou a emitir `perfil`, que é o endereço do "
        "CABEÇALHO (o perfil de JOGO, dono `pacotes.topo`). Como o piloto usa "
        "`setdefault`, quem chega primeiro ganha — e este pacote chega primeiro.")
    # E a prova do outro lado: com o pacote calado, o dono certo escreve.
    carga = pacotes.normalizar(p, {})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)
    assert carga["mesa"]["perfil"] == "meu_perfil", (
        f"o cabeçalho ficou com {carga['mesa']['perfil']!r} e o daemon publica "
        f"'meu_perfil'.")


def test_tudo_o_que_o_pacote_emite_e_endereco_desta_pagina(a09, ctx):
    """Nenhuma chave com nome de CAMADA — só endereço da tela (ou `-cls`).

    `frase`, `autostart` e `registro` são os nomes que `gui/aba_sistema.pacote`
    usa internamente; os da página são `bateria-frase`, `hefesto-autostart` e
    `registro-texto`. Emitir os primeiros escreve em lugar nenhum e esconde o
    fato de que os segundos não estão sendo escritos.

    **A MORDIDA:** acrescente `fora["frase"] = bruto["frase"]` e este teste
    reprova nomeando a chave. Executada:

        AssertionError: o pacote emite chaves que não são endereço desta
        página nem `-cls`: ['frase']
    """
    import pacotes

    from hefesto_dualsense4unix.gui import aba_sistema

    conhecidos = set(aba_sistema.ENDERECOS) | _campos_da_pagina()
    # O QUE VIRA VALOR DE TELA TEM DONO, E ELE NÃO É ESTA RÉGUA: quem separa
    # "chave de contrato" (`mesa`, `colunas`, `blocos`, `cobertura`, `sem_dono`)
    # de "endereço a escrever" é `pacotes.normalizar`, e é dele que sai a lista
    # medida aqui. A versão anterior digitava `("sem_dono", "cobertura")` e por
    # isso ACUSOU o `blocos:` dos rótulos dos botões destrutivos (03/09/2026) —
    # uma chave de contrato que o piloto consome desde 01/09. Régua que digita o
    # que devia perguntar reprova a melhora; é a lição mais cara desta casa.
    p = a09.pacote(ctx)
    estranhas = sorted(
        k for k in pacotes.normalizar(p)["mesa"]
        if not k.endswith("-cls") and k not in conhecidos)
    assert not estranhas, (
        f"o pacote emite chaves que não são endereço desta página nem `-cls`: "
        f"{estranhas}. O nome que a CAMADA usa por dentro não é o endereço da "
        f"tela — e uma chave dessas escreve em lugar nenhum, calada.")


def test_o_que_nao_chega_na_tela_esta_declarado(a09, ctx):
    """Endereço que o produto sabe responder e a pintura não sabe escrever.

    Os três (`hefesto-autostart`, `bateria-perfil`, `bateria-frase`) dependem de
    escrita que não é texto — classe, ou um endereço que a página não tem. Ficam
    em `NAO_CHEGA_NA_TELA` com a razão, para ninguém "ligar" duas vezes o que já
    está lido. E o teste cobra a outra metade: eles NÃO podem ser emitidos, ou
    a pintura os escreveria por cima do interruptor e dos três botões.
    """
    p = a09.pacote(ctx)
    for endereco, razao in a09.NAO_CHEGA_NA_TELA.items():
        assert razao.strip(), f"`{endereco}` está declarado sem razão"
        assert endereco not in p, (
            f"`{endereco}` está declarado como inalcançável E está sendo "
            f"emitido. Se ele passou a ter caminho, tire-o da declaração; se "
            f"não, escrevê-lo apaga o widget que mora naquele endereço.")


# ---------------------------------------------------------------------------
# 3. O exame vem do DADO
# ---------------------------------------------------------------------------
def test_a_contagem_do_exame_sai_da_lista_e_guarda_o_separador(a09):
    """`N linhas · nenhum aviso`, com o `·` dentro do `<span class="sep">`.

    O "8" do desenho é literal de bancada e seria falso na primeira máquina que
    não tivesse oito — esta tem seis. E o separador tem classe própria no
    desenho: escrever a frase como texto puro apagaria o `<span>` e mudaria a
    cor do `·` na tela dela.

    **A MORDIDA:** troque o `.replace(" · ", …)` por `return html.escape(...)`
    e este teste reprova por falta do `<span class="sep">`.
    """
    saida = a09._html_da_contagem("6 linhas · nenhum aviso")
    assert '<span class="sep">·</span>' in saida, (
        f"o separador perdeu a classe do desenho: {saida!r}")
    assert saida.startswith("6 linhas"), saida
    assert a09._html_da_contagem(None) == ""


def test_a_lista_do_exame_tem_uma_linha_por_achado(a09):
    """Seis achados viram seis `.saude`, em duas colunas, e nada mais.

    O desenho tem OITO blocos fixos; `storm_report` devolve de seis a oito. A
    lista se troca INTEIRA (`data-hef-alvo="html"`) porque não existe endereço
    para uma linha que ainda não existe.
    """
    exame = {"linhas": [{"selo": "OK", "cls": "ok", "g": "✓", "txt": f"achado {i}"}
                        for i in range(6)],
             "contagem": "6 linhas · nenhum aviso", "vazio": ""}
    html_ = a09._html_do_exame(exame)
    assert html_.count('class="saude"') == 6, html_
    assert html_.count('class="col-lista"') == 2, html_
    # o corte é `ceil(len/2)`, o mesmo do gerador
    esquerda = html_.split('<div class="risco">')[0]
    assert esquerda.count('class="saude"') == 3, esquerda


def test_a_lista_do_exame_escapa_a_frase_do_produto(a09):
    """A frase vem do `doctor`, não daqui. Um `<` dela não pode virar tag.

    **A MORDIDA:** tire o `html.escape` de `_linha_do_exame` e este teste
    reprova. Executada:

        AssertionError: a frase do produto entrou crua no HTML da tela.
    """
    exame = {"linhas": [{"selo": "OK", "cls": "ok", "g": "✓",
                         "txt": '<b>x</b> & "y"'}],
             "contagem": "1 linha · nenhum aviso", "vazio": ""}
    html_ = a09._html_do_exame(exame)
    assert "<b>x</b>" not in html_, "a frase do produto entrou crua no HTML da tela."
    assert "&lt;b&gt;x&lt;/b&gt;" in html_, html_


def test_o_exame_vazio_diz_qual_dos_dois_vazios_e(a09):
    """`None` (não respondeu) e `[]` (nada a relatar) não podem virar o mesmo.

    A camada do produto já escreveu as duas frases; o que este teste tranca é
    que a lista vazia leve a frase à tela em vez de um painel em branco.
    """
    html_ = a09._html_do_exame(
        {"linhas": [], "contagem": "—",
         "vazio": "O exame não respondeu — não dá para dizer o que esta máquina tem."})
    assert "O exame não respondeu" in html_, html_
    assert 'class="saude"' in html_, html_


def test_o_endereco_do_exame_existe_na_bancada(a09, ctx):
    """Os dois endereços do exame existem no desenho de HOJE, com o alvo `html`.

    A BANCADA e não o publicado, de propósito: a marcação nasceu aqui em
    02/09/2026 e o produto só a recebe pelo `--publicar 09`, que é ato DELA.
    Apontar esta régua para o publicado daria VERMELHO sobre trabalho feito —
    e apontá-la para lá depois da publicação continuará dando verde.
    """
    import onde

    doc = onde.pagina("09-sistema.html").read_text(encoding="utf-8")
    for endereco in ("exame-contagem", "exame-lista"):
        assert f'data-campo="{endereco}"' in doc, (
            f"o gerador parou de marcar `{endereco}` na bancada — o exame volta "
            f"a mostrar os oito achados de bancada do `aba09.py`.")
    assert doc.count('data-hef-alvo="html"') >= 2, (
        "os dois endereços do exame perderam o alvo `html`: a pintura passaria "
        "a escrever a marcação como TEXTO na tela dela.")
    p = a09.pacote(ctx)
    assert p["exame-lista"].startswith('<div class="col-lista">'), p["exame-lista"][:80]


# ---------------------------------------------------------------------------
# 4. O painel de registro não pisca
# ---------------------------------------------------------------------------
def test_o_repouso_do_painel_e_o_da_camada_e_nao_o_do_mockup(a09, ctx):
    """Sem ninguém ter clicado, o painel mostra o que o PRODUTO responde.

    O QUE ISSO ARRANCA: enquanto ninguém escrevia neste endereço, o painel
    ficava com as quatro linhas do mockup — `[23:41:02] daemon pronto · 2
    controles`, `perfil "Mortal Kombat" aplicado aos 2`. Nenhuma aconteceu.

    **FATO SUBSTITUÍDO — 03/09/2026.** Este teste exigia o travessão
    (`p[REGISTRO] == "—"`), e o travessão era o repouso de então: a nota de
    `aba_sistema.SEM_FONTE` dizia que não havia método de IPC que devolvesse o
    registro. **A GTK nunca teve um traço aqui:** o `Gtk.TextView` dela fica
    sempre com a saída de `systemctl status <unit>` (`daemon_actions.py:1970` e
    `:2549`). O repouso passou a ser o mesmo dela, mais a identidade de fábrica
    (decisão 10). O que este teste guarda continua sendo o mesmo: **o repouso é
    do PRODUTO, e nunca as quatro linhas inventadas do mockup.**

    **A MORDIDA:** tire `fora[REGISTRO] = _no_painel(...)` do `pacote()` e este
    teste reprova. Executada:

        KeyError: 'registro-texto'
    """
    p = a09.pacote(ctx)
    assert p[a09.REGISTRO], "o painel voltou a não ser escrito por ninguém"
    assert "23:41" not in p[a09.REGISTRO], (
        "as quatro linhas inventadas do mockup voltaram ao painel.")
    assert "Mortal Kombat" not in p[a09.REGISTRO]


def test_o_que_o_gesto_escreve_no_painel_sobrevive_ao_tique(a09, ctx):
    """O tique seguinte repinta o MESMO texto, em vez de apagá-lo.

    A pintura corre a cada 500 ms. Sem `_PAINEL`, as oitenta linhas do registro
    apareceriam e sumiriam antes de ela terminar de ler.

    **A MORDIDA:** troque `_para_o_painel(texto)` por
    `{"mesa": {REGISTRO: texto}}` em `ver_detalhes` e este teste reprova.
    Executada:

        AssertionError: o tique seguinte apagou o que o gesto escreveu: '—'
    """
    resposta = a09._para_o_painel("linha do journal")
    assert resposta == {"mesa": {a09.REGISTRO: "linha do journal"}}
    depois = a09.pacote(ctx)
    assert depois[a09.REGISTRO] == "linha do journal", (
        f"o tique seguinte apagou o que o gesto escreveu: "
        f"{depois[a09.REGISTRO]!r}")


# ---------------------------------------------------------------------------
# O CSS: `1fr` cru não volta às faixas internas
# ---------------------------------------------------------------------------
def test_nenhuma_faixa_desta_aba_volta_ao_1fr_cru():
    """`.bloco2` e `.saude-cols` medem `minmax(0,1fr)`, e a régua do gerador cobra.

    MEDIDO em 02/09/2026, no Chrome (1920x1080), com os valores REAIS: os quatro
    botões do serviço estouravam 27px por cima do Perfil de Bateria, e a segunda
    coluna do exame estourava 253px por cima de "Preparar os jogos". Com os
    textos do desenho, os dois davam 41px de folga — o defeito só existia com
    dado de verdade dentro.

    **A MORDIDA:** volte `.bloco2` a `1fr 1px 184px` e o PRÓPRIO GERADOR recusa
    a rodar (régua 5), antes deste teste. Este aqui é a segunda trava, para o
    dia em que alguém editar o HTML sem passar pelo gerador.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba09.py").read_text(
        encoding="utf-8")
    for faixa in (".bloco2", ".saude-cols"):
        regra = re.search(re.escape(faixa) + r"\{[^}]*grid-template-columns:([^;]*);",
                          fonte)
        assert regra, f"a faixa `{faixa}` sumiu do gerador — a régua ficou cega"
        assert not re.search(r"(^|\s)1fr", regra.group(1)), (
            f"a faixa `{faixa}` voltou ao `1fr` cru: {regra.group(1).strip()!r}. "
            f"O piso de `1fr` é o CONTEÚDO, e com os valores REAIS desta aba "
            f"isso estoura 27px (`.bloco2`) e 253px (`.saude-cols`).")
    assert '".bloco2", ".saude-cols"' in fonte, (
        "as duas faixas internas saíram da lista da régua 5 do gerador — foi "
        "por estarem de fora dela que o `1fr` cru sobreviveu ali.")
