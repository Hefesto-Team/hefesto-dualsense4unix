#!/usr/bin/env python3
"""O LUGAR SEM DONO ganha travessão — e o molde nunca alcança o DESENHO.

POR QUE ELA EXISTE, fotografado em 02/09/2026 com um dublê de estado sem
controle nenhum (`mesa_viva.estado_do_daemon` devolvendo `controllers: []`, para
não desconectar o controle dela): o topo dizia `0 controles: 0 USB · 0 BT` e a
MESMA tela, logo abaixo, mostrava `P1 · Cosmic Red · USB` com bateria 100%,
touchpad "Tocando", barra de luz `#7EB8D4`, microfone `ATIVO` e um
`P2 · Starlight Blue · BT · 64%`. Nada disso existia.

A CAUSA não é de nenhuma das dez abas. O piloto já apaga os lugares sem dono
(`hefesto_vivo.py:1005-1016`), mas as CHAVES que ele apaga são a união do que as
colunas VIVAS trouxeram — e com zero controles não há coluna viva nenhuma.
`set()` de chaves faz `dict.fromkeys(chaves, "—")` devolver `{}`.

Medido pela régua do mockup, a mesma árvore, só mudando a mesa:

    ANTES   mesa VAZIA (0 controles)  330 campos: 114 PRODUTO · 179 MOCKUP
    DEPOIS  mesa VAZIA (0 controles)  330 campos: 184 PRODUTO · 109 MOCKUP
    mesa CHEIA (2 controles)          330 campos: 188 PRODUTO ·  68 MOCKUP
                                      (inalterada — o molde se cala com dono)

A MORDIDA, e são três, cada uma reprovando um teste diferente:

1. troque `LUGAR_SEM_DONO = "*"` por `"p1"` — a moldura do lugar vazio morre,
   porque o piloto deixa de contar aquele lugar como sem dono;
2. apague o filtro `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE` — a barra da bateria volta
   a receber travessão, o CSSOM recusa `width: "—%"` e o contador de pintura
   soma +1 por tique para sempre;
3. troque a fonte do molde pela PÁGINA (os `data-campo` de dentro do
   `[data-controle="pN"]`) — e a `05-vibracao` perde os botões "Testar" e
   "Parar" e o SVG do controle.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Um controle de mentira. MAC da faixa sintética da casa — há dois portões de
#: anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
COM_DONO = {"uniq": UNIQ, "connected": True, "transport": "usb",
            "battery_pct": 95, "inputs": {}, "audio": {}, "speaker": {}}
MESA_COM_DONO = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
                  "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

ESTADO = {"active_profile": "regua", "rumble_policy": "balanceado",
          "controllers": []}

#: OS QUATRO LUGARES do desenho, como o piloto os conhece
#: (`hefesto_vivo.TODOS_OS_LUGARES`). Repetidos aqui porque importar o piloto
#: puxaria GTK e WebKit para dentro da suíte; `test_o_piloto_ainda_aplica_o_molde`
#: confere que a lista continua a mesma lá.
LUGARES = {"p1", "p2", "p3", "p4"}


@pytest.fixture
def pacotes_mod():
    import pacotes

    pacotes._MOLDE.clear()
    pacotes._ALVOS.clear()
    pacotes._LUGARES.clear()
    return pacotes


def test_o_molde_nao_roda_a_pintura_de_quem_nao_tem_lugar(pacotes_mod):
    """FATO DERRUBADO: as funções de pacote NÃO são todas puras.

    O alto de `pacotes/__init__.py` promete que "nenhuma função de pacote toca
    GTK, WebView ou IPC — elas são puras, e é por isso que dá para testá-las sem
    abrir janela". `a10_perfis._uma_vez_so:214` guarda `_PINTADO_PARA` e
    `_ULTIMO_TIQUE` em MÓDULO, para não repintar os três campos que ELA DIGITA
    enquanto ela digita. Rodar a pintura duas vezes no mesmo tique troca esse
    estado — e no tique seguinte o produto volta a escrever por cima do nome que
    ela está digitando.

    Foi um teste que achou: `test_o_casamento_das_dez` passa sozinho e reprovava
    depois desta régua rodar, com a `10-perfis` casando 8 endereços em vez de 10
    — os três campos dela sumiam da carga.

    A MORDIDA: tire a trava `lugares_da_pagina(...)` de `molde_do_lugar` e este
    teste reprova nomeando o campo que se mexeu.
    """
    from pacotes import a10_perfis

    ctx = pacotes_mod.Contexto(state=ESTADO, mesa=[], conectados=[], estados={})
    antes = (a10_perfis._PINTADO_PARA, a10_perfis._ULTIMO_TIQUE,
             a10_perfis._ESCOLHIDO)
    assert pacotes_mod.molde_do_lugar("10-perfis.html", ctx, {}) == {}
    depois = (a10_perfis._PINTADO_PARA, a10_perfis._ULTIMO_TIQUE,
              a10_perfis._ESCOLHIDO)
    assert antes == depois, (
        "o molde rodou a pintura da 10-perfis e mexeu na memória dela — no "
        f"tique seguinte o produto repinta o que ela digita. antes={antes} "
        f"depois={depois}")
    assert not pacotes_mod.lugares_da_pagina("10-perfis.html"), (
        "a 10-perfis ganhou lugar de controle — a trava precisa de outra razão")


def _mesa_vazia(pacotes_mod):
    return pacotes_mod.Contexto(state=ESTADO, mesa=[], conectados=[], estados={})


def _o_que_o_piloto_faz(pacotes_mod, carga):
    """As cinco linhas de `hefesto_vivo.py:1005-1016`, replicadas.

    NÃO É DIGITAR O QUE SE DEVIA LER: o piloto só existe dentro de uma
    `Gtk.Window` com WebKit, e importá-lo aqui traria a janela para a suíte. O
    que impede esta cópia de envelhecer calada é
    `test_o_piloto_ainda_aplica_o_molde`, que LÊ o arquivo dele e reprova se
    aquelas linhas mudarem sem esta mudar junto.
    """
    chaves = set()
    for campos in carga["colunas"].values():
        chaves |= set(campos)
    apagar = sorted(LUGARES - set(carga["colunas"]))
    for pref in apagar:
        carga["colunas"][pref] = dict.fromkeys(chaves, pacotes_mod.TRAVESSAO)
    carga["vazios"] = apagar
    return carga


# ---------------------------------------------------------------------------
# 1. o molde se cala quando há dono — o piloto já se vira
# ---------------------------------------------------------------------------
def test_com_controle_na_mesa_o_molde_se_cala(pacotes_mod):
    """Com UMA coluna viva, a união das chaves dela é melhor que o molde.

    Ela é DADO; o molde é só a lista de nomes. Emitir os dois faria o
    despachante competir com a aba pelo mesmo endereço.
    """
    ctx = pacotes_mod.Contexto(state=ESTADO, mesa=MESA_COM_DONO,
                               conectados=[COM_DONO], estados={})
    for pagina in sorted(pacotes_mod.PACOTES):
        assert pacotes_mod.molde_do_lugar(pagina, ctx, {}) == {}, (
            f"{pagina}: o molde falou com um controle na mesa — e aí ele "
            "duplica o que a coluna viva já diz")


def test_a_pagina_sem_pacote_continua_devolvendo_none(pacotes_mod):
    """`None` é o estado honesto de uma aba que ninguém pinta — e não mudou.

    O molde não pode transformar esse `None` num dicionário: o piloto distingue
    "ninguém pinta isto ainda" de "pintei nada", e confundir os dois é como uma
    tela morta passa por tela sem novidade.

    FATO DERRUBADO, medido em 02/09/2026: a casa diz em dois lugares que a
    `07-lancadores` é a aba SEM pacote — `hefesto_vivo.SEM_PACOTE` e o
    comentário do `_tique` ("a `07-lancadores` não tem pacote e sai daquele
    `return`"). **Ela tem**: `a07_lancadores.py:236` traz
    `@registrar("07-lancadores.html")`, e `pacote_da_pagina` devolve 26 chaves
    para ela. Por isso este teste usa uma página que de fato não existe.
    """
    ctx = _mesa_vazia(pacotes_mod)
    assert pacotes_mod.pacote_da_pagina("99-nao-existe.html", ctx) is None
    assert "07-lancadores.html" in pacotes_mod.PACOTES, (
        "a 07 perdeu o pacote — e aí o comentário do piloto voltou a valer")


# ---------------------------------------------------------------------------
# 2. com a mesa vazia, o molde nomeia o que a ABA pinta — e nada mais
# ---------------------------------------------------------------------------
def test_o_molde_e_o_que_a_aba_pinta_menos_barra_e_html(pacotes_mod):
    """O molde ⊆ o que a aba emite por controle. Nunca um endereço a mais.

    É esta contenção que impede a destruição: por construção o travessão só
    alcança endereço que a própria aba já escreve.
    """
    import casamento

    ctx = _mesa_vazia(pacotes_mod)
    olhadas = []
    for pagina in sorted(pacotes_mod.PACOTES):
        # SÓ AS PÁGINAS COM LUGAR, e não é atalho: `casamento.do_pacote` roda a
        # pintura, e a da `10-perfis` guarda o instante da última em MÓDULO
        # (`a10_perfis._uma_vez_so:214`). Chamá-la aqui faz `test_o_casamento
        # _das_dez` reprovar segundos depois, com os três campos que ela digita
        # sumindo da carga — foi assim que este teste achou o defeito.
        if not pacotes_mod.lugares_da_pagina(pagina):
            continue
        olhadas.append(pagina)
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        _mesa, da_aba = casamento.do_pacote(pagina, ESTADO)
        assert set(molde) <= set(da_aba), (
            f"{pagina}: o molde alcança {sorted(set(molde) - set(da_aba))}, que "
            "a aba NÃO pinta — é endereço de desenho, não de dado")
    assert len(olhadas) >= 7, (
        f"só {len(olhadas)} páginas com lugar de controle — este teste está "
        "medindo quase nada")


def test_a_barra_e_o_html_ficam_de_fora(pacotes_mod):
    """`largura` e `html` não aceitam travessão, e as duas foram medidas.

    `bateria-barra` da `02-controles` é `data-hef-alvo="largura"`: o piloto
    monta `el.style.width = "—%"`, o CSSOM recusa, a barra fica na largura do
    mockup e o contador de pintura soma +1 por tique para sempre.
    `players` da `04-iluminacao` é `html`: o travessão APAGA os quatro botões
    de jogador.
    """
    ctx = _mesa_vazia(pacotes_mod)
    controles = pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})
    assert "bateria" in controles, "a bateria é TEXTO e tem de ganhar travessão"
    assert "bateria-barra" not in controles, (
        "a barra entrou no molde: `width: \"—%\"` é recusado pelo CSSOM e o "
        "contador de pintura passa a mentir a cada tique")

    ilumina = pacotes_mod.molde_do_lugar("04-iluminacao.html", ctx, {})
    assert "hex" in ilumina
    assert "players" not in ilumina, (
        "`players` é `data-hef-alvo=\"html\"` — travessão ali apaga os quatro "
        "botões de jogador")


def test_o_molde_nao_toca_o_desenho_da_vibracao(pacotes_mod):
    """O achado que derruba o caminho ÓBVIO desta cura.

    Ler a lista de campos da PÁGINA — os `data-campo`/`data-papel` de dentro do
    `[data-controle="pN"]` — parece o caminho natural, e é o que
    `a03_gatilhos._casas_e_barras()` faz para contar casas. Medido na
    `05-vibracao` publicada de 02/09/2026, dentro do lugar do P1 há:

        data-papel="testar"   o BOTÃO "Testar"
        data-papel="parar"    o BOTÃO "Parar"
        data-papel="forca"    quatro vezes: Economia · Balanceado · Máximo · Auto
        data-papel="desenho"  o SVG do controle, com 231 filhos

    Travessão neles apaga os botões e o desenho — o mesmo defeito que a
    Vibração cometeu em 01/09 escrevendo `balanceado` dentro dos quatro degraus.
    """
    ctx = _mesa_vazia(pacotes_mod)
    molde = pacotes_mod.molde_do_lugar("05-vibracao.html", ctx, {})
    assert molde, "a Vibração ficou sem molde — ver `_LUGAR_DE_MENTIRA`"
    for endereco in ("testar", "parar", "forca", "desenho", "lado", "motor"):
        assert endereco not in molde, (
            f"o molde alcançou `{endereco}`, que é DESENHO e não dado — a tela "
            "perderia um botão ou o controle inteiro")

    # e a página TEM esses endereços: sem isto o teste passaria por vacuidade.
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("05-vibracao.html", publicado=True).read_text(encoding="utf-8")
    for endereco in ("testar", "parar", "forca", "desenho"):
        assert f'data-papel="{endereco}"' in doc, (
            f"a página publicada não tem mais `{endereco}` — este teste virou "
            "vácuo e a razão dele mudou")


def test_o_molde_escreve_o_travessao_do_desenho(pacotes_mod):
    """O texto do vazio é DELA, e já está no desenho — nada novo nasce aqui.

    Os lugares P3 e P4 da `02-controles` publicada trazem
    `<span class="leia">—</span>` e `<span class="bat">—</span>`. É esse mesmo
    caractere que o molde escreve.
    """
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")
    vazio = re.search(r'data-controle="p3".*?</div>\s*</div>', doc, re.S)
    assert vazio is not None, "o lugar P3 sumiu da página publicada"
    assert f">{pacotes_mod.TRAVESSAO}<" in vazio.group(0), (
        "o desenho deixou de usar o travessão no lugar vazio — o texto de tela "
        "é dela, e esta cura tem de seguir o que o desenho faz")

    ctx = _mesa_vazia(pacotes_mod)
    molde = pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})
    assert set(molde.values()) == {pacotes_mod.TRAVESSAO}


# ---------------------------------------------------------------------------
# 3. a carga inteira: os quatro lugares apagados E a moldura de vazio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pagina", ["01-jogar.html", "02-controles.html",  # (noqa-acento)
                                    "04-iluminacao.html", "05-vibracao.html"])
def test_os_quatro_lugares_ficam_no_travessao_e_marcados(pacotes_mod, pagina):
    """O desfecho que a foto cobra: nada de dado, e a moldura de vazio acesa.

    A `carga["vazios"]` é o que faz o piloto marcar `data-conectado="nao"` e a
    classe `off`. Emitir o molde nas colunas de `p1`…`p4` a esvaziaria — é por
    isso que ele mora em `LUGAR_SEM_DONO`.
    """
    ctx = _mesa_vazia(pacotes_mod)
    bruto = pacotes_mod.pacote_da_pagina(pagina, ctx)
    assert bruto is not None
    carga = pacotes_mod.normalizar(bruto, {})

    assert pacotes_mod.LUGAR_SEM_DONO in carga["colunas"], (
        f"{pagina}: o molde não chegou à carga")
    assert not (LUGARES & set(carga["colunas"])), (
        f"{pagina}: um lugar do desenho veio ocupado na carga — o piloto vai "
        "deixar de marcá-lo como vazio e a moldura fica de CONECTADO")

    carga = _o_que_o_piloto_faz(pacotes_mod, carga)
    assert sorted(carga["vazios"]) == sorted(LUGARES), (
        f"{pagina}: os quatro lugares tinham de estar na lista de vazios")
    for pref in LUGARES:
        valores = set(carga["colunas"][pref].values())
        assert valores == {pacotes_mod.TRAVESSAO}, (
            f"{pagina}/{pref}: sobrou valor que não é travessão: {valores}")
    assert carga["colunas"]["p1"], (
        f"{pagina}: o lugar P1 ficou sem campo nenhum — é o estado de ANTES "
        "desta cura, em que o desenho continuava na tela")


def test_o_molde_nao_pousa_em_lugar_nenhum_da_pagina(pacotes_mod):
    """`LUGAR_SEM_DONO` não pode ser um `data-controle` de nenhuma página.

    Se fosse, o molde escreveria travessão num lugar de verdade — e o piloto
    deixaria de contá-lo como vazio.
    """
    from hefesto_dualsense4unix.interface import onde

    for caminho in onde.paginas(publicado=True):
        doc = caminho.read_text(encoding="utf-8")
        alvo = f'data-controle="{pacotes_mod.LUGAR_SEM_DONO}"'
        assert alvo not in doc, f"{caminho.name} tem {alvo} — o molde pousaria nele"


# ---------------------------------------------------------------------------
# 4. o acoplamento com o piloto, declarado e conferido
# ---------------------------------------------------------------------------
def test_o_piloto_ainda_aplica_o_molde():
    """As duas pontas têm de mudar no mesmo commit.

    O molde só vira travessão na tela porque o piloto apaga os lugares sem dono
    com a UNIÃO das chaves das colunas. Este teste LÊ o arquivo dele — não
    digita o que ele faz — e reprova se aquele trecho sumir, porque nesse dia o
    molde vira uma coluna que não pinta nada e ninguém acusaria.
    """
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    assert 'dict.fromkeys(chaves, "—")' in piloto, (
        "o piloto deixou de apagar os lugares sem dono com a união das chaves "
        "— o molde do despachante ficou sem quem o aplique")
    assert 'carga["vazios"] = apagar' in piloto, (
        "o piloto deixou de marcar a moldura dos lugares sem dono")
    assert 'TODOS_OS_LUGARES = {"p1", "p2", "p3", "p4"}' in piloto, (
        "os quatro lugares do desenho mudaram no piloto e não aqui")
