#!/usr/bin/env python3
"""O LUGAR SEM DONO ganha travessão — e o molde nunca alcança o DESENHO.

POR QUE ELA EXISTE, fotografado em 02/09/2026 com um dublê de estado sem
controle nenhum (`mesa_viva.estado_do_daemon` devolvendo `controllers: []`, para
não desconectar o controle dela): o topo dizia `0 controles: 0 USB · 0 BT` e a
MESMA tela, logo abaixo, mostrava `P1 · Cosmic Red · USB` com bateria 100%,
touchpad "Tocando", barra de luz `#7EB8D4`, microfone `ATIVO` e um
`P2 · Starlight Blue · BT · 64%`. Nada disso existia.

A CAUSA não é de nenhuma das dez abas. O piloto já apaga os lugares sem dono
(por `pacotes.apagar_os_lugares_sem_dono`), mas as CHAVES que ele apaga são a
união do que as colunas VIVAS trouxeram — e com zero controles não há coluna
viva nenhuma.
`set()` de chaves faz `dict.fromkeys(chaves, "—")` devolver `{}`.

Medido pela régua do mockup em 02/09/2026, `--voltas-por-aba 8 --sem-cor`, só
mudando a MESA — e o número é da mesa, então dizer qual mesa é obrigatório:

                                        campos  PRODUTO  MOCKUP  INDECID
    mesa VAZIA, sem esta cura              330      114     179       37
    mesa VAZIA, com esta cura              330      184     109       37
    mesa CHEIA (2 controles: 1 USB, 1 BT)  330      188      68       74
                                           (igual com e sem — o molde se cala
                                            quando há dono)

AS TRÊS LINHAS SÃO DESTA CURA SOZINHA, e a árvore andou desde então: com o SELO
DA VISITA junto (a outra metade da fundação), o INDECIDÍVEL vai a zero e as
mesmas medições dão `222 · 108 · 0` com a mesa vazia sem o filtro dos filhos
mudos, `218 · 112 · 0` com ele, e `262 · 68 · 0` com a mesa cheia.

OS QUATRO CAMPOS DE DIFERENÇA NA MESA VAZIA SÃO ENTREGA, e não regressão: eram
o travessão DESTRUINDO desenho que o texto não sabe refazer, e a régua contava
destruição como pintura. Ver `enderecos_que_o_texto_apaga`.

A MORDIDA, e são SEIS, cada uma reprovando um teste diferente:

1. troque `LUGAR_SEM_DONO = "*"` por `"p1"` — a moldura do lugar vazio morre,
   porque o piloto deixa de contar aquele lugar como sem dono;
2. apague o filtro `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE` — a barra da bateria volta
   a receber travessão, o CSSOM recusa `width: "—%"` e o contador de pintura
   soma +1 por tique para sempre;
3. troque a fonte do molde pela PÁGINA (os `data-campo` de dentro do
   `[data-controle="pN"]`) — e a `05-vibracao` perde os botões "Testar" e
   "Parar" e o SVG do controle;
4. arranque a trava `lugares_da_pagina()` de `molde_do_lugar` — a memória de
   módulo da `10-perfis` se mexe e o produto volta a escrever por cima do nome
   que ela está digitando. **Esta é a que a docstring esquecia**, e é a única
   que morde o fato derrubado no alto deste arquivo: quem contasse três
   deixaria de fora a mais importante;
5. tire `enderecos_que_o_texto_apaga` do filtro do molde — o ponto verde de
   "quem navega o PC" volta a ser apagado, e ele NÃO volta quando o controle
   volta;
6. troque a chave do cache do molde, que é `(página, perfil ativo)`, por uma
   só com a página — a `03-gatilhos` passa a servir o molde do perfil anterior.
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

#: OS QUATRO LUGARES do desenho. Eles NÃO são mais repetidos aqui: desde
#: 02/09/2026 moram em `pacotes.TODOS_OS_LUGARES`, ao lado da conta que os
#: apaga, e este teste lê a mesma constante que o produto lê.
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
    """A CONTA DE VERDADE, chamada — não replicada.

    ELA ERA UMA CÓPIA, e a cópia era o defeito. As cinco linhas viviam dentro do
    `hefesto_vivo.py` (que não se importa aqui: traria GTK e WebKit para a
    suíte), e a régua que guardava o acoplamento cobrava três LITERAIS daquele
    arquivo. Medido em 02/09/2026: acrescentar `if pref_ == "*": continue` ao
    laço da união mata a cura inteira — a régua do mockup volta ao
    `330 · 114 · 179 · 37` da mesa vazia — e os três literais continuam lá, com
    13 testes verdes.

    Agora a conta mora no despachante (`pacotes.apagar_os_lugares_sem_dono`), o
    piloto a CHAMA, e este teste chama a MESMA função. Não há mais o que
    envelhecer em silêncio.
    """
    return pacotes_mod.apagar_os_lugares_sem_dono(carga)


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

    A CONTENÇÃO É VERDADEIRA, E NÃO É A GARANTIA QUE ESTE TEXTO DIZIA. A frase
    que estava aqui — *"é esta contenção que impede a destruição"* — caiu em
    02/09/2026: "a aba pinta este endereço" não prova "este endereço é FOLHA".
    A `06-navegacao` pinta `navega`, e o travessão nele apagou o
    `<span class="bolinha">` para sempre. Quem impede a destruição é o par desta
    asserção com `test_o_travessao_nao_pousa_em_marca_que_o_texto_nao_devolve`.

    E ELA PASSA POR VACUIDADE COM MOLDE VAZIO — `set() <= qualquer coisa` é
    sempre verdadeiro. O piso por página está em
    `test_o_molde_de_cada_pagina_nao_encolhe`.
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


#: QUANTOS CAMPOS O MOLDE DE CADA PÁGINA TEM, medido em 02/09/2026 com a mesa
#: vazia. O piso existe porque `set(molde) <= set(da_aba)` — a única asserção
#: que percorria as sete — é VERDADEIRA POR VACUIDADE quando o molde é `{}`.
#: Medido: fazer `molde_do_lugar` devolver `{}` para a `03-gatilhos`
#: tirava 22 campos da aba de mais peso (a régua do mockup voltava a
#: `03-gatilhos 52 · 3 · 49 · 0`, o número de ANTES da cura) e os 13 testes
#: ficavam verdes. E não é hipótese remota: `molde_do_lugar` engole a pintura do
#: fantasma com `except Exception: seria = {}`, sem log — qualquer regressão que
#: faça a pintura levantar sob o `_CONTROLE_DE_MENTIRA` apaga o molde daquela
#: aba em silêncio.
#:
#: A `06-navegacao` é ZERO DE PROPÓSITO e a razão está escrita: o único campo
#: por controle dela é `navega`, e `navega` é o endereço cujo filho MUDO o
#: travessão apaga (`enderecos_que_o_texto_apaga`). Um número maior aqui quer
#: dizer que alguém devolveu o ponto verde à fila de destruição.
PISO_DO_MOLDE = {
    "01-jogar.html": 3,
    "02-controles.html": 8,
    # 22 ATÉ 02/09/2026, E A QUEDA É A CURA — não uma regressão. Doze dos 22
    # eram as `aj-*` da caixa de ajustes, e o molde as apagava uma a uma com
    # travessão. A decisão 2 dela (*"os ajustes viram lista e a caixa acompanha
    # o modo"*) tirou a caixa da pintura campo a campo: ela virou um BLOCO, e o
    # pacote troca a caixa inteira de TODO lugar sem aparelho — inclusive o P2,
    # que a página dá por conectado e o molde nunca alcançava com um controle
    # só na mesa. A garantia ficou mais forte e o número, menor.
    #
    # A régua que cobra a caixa vazia agora é
    # `test_a_caixa_do_lugar_sem_aparelho_tambem_e_trocada`, em
    # `test_a_aba_gatilhos_nao_deixa_o_mockup_na_tela.py`.
    "03-gatilhos.html": 10,
    "04-iluminacao.html": 4,
    "05-vibracao.html": 4,
    "06-navegacao.html": 0,
    "08-conexoes.html": 6,
}


def test_o_molde_de_cada_pagina_nao_encolhe(pacotes_mod):
    """O molde de uma aba inteira podia ir a ZERO sem um teste piscar.

    Só QUATRO das SETE páginas com lugar estavam no parametrize do desfecho, e a
    única asserção que percorria as sete passava por vacuidade com molde vazio.
    Aqui as sete têm PISO, e o piso é o número medido.
    """
    ctx = _mesa_vazia(pacotes_mod)
    com_lugar = [p for p in sorted(pacotes_mod.PACOTES)
                 if pacotes_mod.lugares_da_pagina(p)]
    assert set(com_lugar) == set(PISO_DO_MOLDE), (
        f"as páginas com lugar de controle mudaram: {sorted(com_lugar)} — o "
        "piso do molde precisa acompanhar")
    for pagina in com_lugar:
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        assert len(molde) >= PISO_DO_MOLDE[pagina], (
            f"{pagina}: o molde caiu de {PISO_DO_MOLDE[pagina]} para "
            f"{len(molde)} campos. O lugar vazio voltou a mostrar o desenho "
            f"em {PISO_DO_MOLDE[pagina] - len(molde)} endereços, e nenhuma "
            "outra régua acusaria")


def test_o_travessao_nao_pousa_em_marca_que_o_texto_nao_devolve(pacotes_mod):
    """A CONTENÇÃO NÃO ERA A GARANTIA QUE O TEXTO DIZIA.

    A docstring de `test_o_molde_e_o_que_a_aba_pinta_menos_barra_e_html`
    afirmava: *"por construção o travessão só alcança endereço que a própria aba
    já escreve"*. É verdade — e não basta. "A aba pinta este endereço" não prova
    "este endereço é FOLHA": `navega` é pintado pela `06-navegacao` e tem
    `<span class="bolinha"></span>` dentro, um filho MUDO que só o CSS desenha.
    O alvo `texto` escreve `el.textContent` e apaga os filhos; o texto devolve
    `<span class="pt">•</span>` (o ponto está no texto) e NÃO devolve a bolinha.

    MEDIDO com o piloto de verdade, dublê de tempo, `--oculta`, na `06`::

        antes  1-mesa-vazia filhos=0 '—' · 2-o-controle-voltou filhos=0 'USB • …'
        depois 1-mesa-vazia filhos=2 'USB • …' · 2-o-controle-voltou filhos=2

    Sem esta régua o dano ficava em pé com as treze anteriores verdes.
    """
    ctx = _mesa_vazia(pacotes_mod)
    for pagina in sorted(pacotes_mod.PACOTES):
        if not pacotes_mod.lugares_da_pagina(pagina):
            continue
        apaga = pacotes_mod.enderecos_que_o_texto_apaga(pagina)
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        assert not (set(molde) & apaga), (
            f"{pagina}: o molde alcança {sorted(set(molde) & apaga)} — o "
            "travessão apagaria uma marca que o texto não sabe devolver, e ela "
            "não volta nem quando o controle volta")

    # e a leitura da página tem de estar ENXERGANDO alguma coisa: sem isto o
    # teste acima passaria por vacuidade no dia em que o parser quebrasse.
    assert pacotes_mod.enderecos_que_o_texto_apaga("06-navegacao.html") == {
        "navega"}, (
        "a `06-navegacao` publicada perdeu o `<span class=\"bolinha\">` dentro "
        "do `navega` — a razão desta régua mudou")
    # A SEGUNDA ÂNCORA MUDOU DE ENDEREÇO — 03/09/2026, fato substituído. Ela era
    # `04-iluminacao·aceso`, e o `aceso` NÃO EXISTE MAIS na página publicada: a
    # cura de 02/09 renomeou o endereço para `luz`, com alvo `html`, justamente
    # para o `el.textContent` parar de apagar as duas tiras e as cinco lâmpadas
    # (`a04_iluminacao`, a nota do campo `luz`) — e ela publicou em `3f9160f4`.
    # O `html` já está em `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE`, então aquele
    # desenho passou a ser poupado por OUTRA porta, e não por esta.
    #
    # A SEGUNDA ÂNCORA É DESCOBERTA, E NÃO DIGITADA — 03/09/2026, e esta é a
    # TERCEIRA vez que ela troca de nome. Foi `04-iluminacao·aceso`, virou
    # `04-iluminacao·troca.item`, e o `troca.item` saiu da lista quando outra
    # frente lhe deu `data-hef-alvo="plastico"` — o alvo `texto` deixou de
    # tocá-lo, e ele passou a ser poupado por OUTRA porta.
    #
    # Ou seja: a âncora envelheceu porque o produto MELHOROU, e a régua reprovou
    # a melhora. É a forma que esta casa mais pagou em 03/09, e ela apareceu
    # aqui numa guarda de vacuidade — o lugar de onde menos se espera.
    #
    # A guarda continua guardando o que importa: que o conjunto NÃO seja vazio
    # em toda a árvore. Qual página o sustenta é dado, não requisito.
    onde_ha_mudo = {
        pagina: sorted(pacotes_mod.enderecos_que_o_texto_apaga(pagina))
        # A LISTA DAS DEZ TEM DONO: `pacotes.PACOTES` é a tabela que diz qual
        # pacote pinta cada página, e é ela que o despachante consulta.
        for pagina in sorted(pacotes_mod.PACOTES)
    }
    com_mudo = {k: v for k, v in onde_ha_mudo.items() if v}
    assert com_mudo, (
        "NENHUMA página tem filho mudo sob alvo `texto` — o teste acima passa "
        "por vacuidade, e a exceção que ele mede deixou de ter caso. Se isso é "
        "verdade de propósito (todo elemento com filho mudo ganhou outro alvo), "
        "apague os dois; se não é, alguém apagou desenho.\n"
        f"medido: {onde_ha_mudo}")


def test_o_travessao_nao_pousa_no_fundo_nem_na_barra(pacotes_mod):
    """A composição do conjunto é cobrada, e cada nome tem a sua razão.

    `fundo` faltava, e sofre a MESMA recusa do CSSOM que tirou `largura`: o ramo
    do `escrever()` é `if(el.style.background !== t){ … return 1; }`, e
    `background: "—"` nunca volta igual — o contador soma +1 por tique para
    sempre. Hoje é latente (zero páginas com esse alvo), e é por isso que ele
    tinha de entrar ANTES do primeiro.
    """
    medidos = {"largura", "html", "fundo"}
    assert medidos == pacotes_mod.ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE, (
        "o conjunto mudou: cada alvo aqui custou uma medição, e sair dele "
        "devolve um defeito de contador ou de marcação à tela")

    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    assert "if(el.style.background !== t){ el.style.background = t; return 1; }" \
        in piloto, (
        "o ramo `fundo` do `escrever()` mudou — se ele passou a escrever e "
        "COMPARAR (como o `cor` faz), o travessão deixou de mentir no contador "
        "e este nome pode sair do conjunto")


def test_o_molde_da_gatilhos_muda_com_o_perfil_e_o_cache_sabe(pacotes_mod):
    """O perfil está na chave do cache PORQUE ele muda o molde — medido.

    A `03-gatilhos` nomeia os ajustes DO PERFIL (`aj-nome-d-2`, `aj-val-d-2`,
    `aj-pct-d-2`), então um cache só por página serviria o molde do perfil
    anterior: quem abrisse a aba num perfil e trocasse para outro ficaria com
    endereços servidos pelo molde velho, mostrando o valor que o mockup cravou
    nos quatro lugares vazios — o defeito que esta cura existe para matar.

    NENHUM TESTE COBRIA A CHAVE: tirar o perfil dela deixava os treze
    verdes. Aqui a chave é lida, e o cache tem de ter uma entrada POR PERFIL.
    """
    pacotes_mod._MOLDE.clear()
    for perfil in ("um-perfil", "outro-perfil"):
        ctx = pacotes_mod.Contexto(
            state={**ESTADO, "active_profile": perfil}, mesa=[], conectados=[],
            estados={})
        pacotes_mod.molde_do_lugar("03-gatilhos.html", ctx, {})
    guardadas = [k for k in pacotes_mod._MOLDE if k[0] == "03-gatilhos.html"]
    assert sorted(guardadas) == [("03-gatilhos.html", "outro-perfil"),
                                 ("03-gatilhos.html", "um-perfil")], (
        "o cache do molde deixou de separar por perfil — a Gatilhos passa a "
        f"servir o molde do perfil anterior. guardadas={sorted(guardadas)}")


def test_a_aba_que_ja_emite_coluna_dispensa_o_molde(pacotes_mod):
    """A segunda guarda de `molde_do_lugar`, que não tinha régua nenhuma.

    Ela é defesa DECLARADA, não lápide: nenhuma das dez abas emite coluna com a
    mesa vazia hoje (medido), e o comentário dela diz isso. Mas no dia em que
    uma emitir, é esta linha que decide — a união do que a aba trouxe é DADO, e
    melhor que uma lista de nomes no travessão. Arrancá-la (`if False:`) deixava
    os treze verdes.
    """
    ctx = _mesa_vazia(pacotes_mod)
    ja_tem = {"colunas": {"p1": {"bateria": "95%"}}}
    assert pacotes_mod.molde_do_lugar("02-controles.html", ctx, ja_tem) == {}, (
        "a aba já emitiu coluna sem controle nenhum — o molde tem de se calar, "
        "senão ele compete com o dado de verdade pelo mesmo endereço")
    # e sem isso ela FALA: o teste acima passaria por vacuidade se o molde
    # estivesse mudo por outra razão.
    assert pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})


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
    # OS DOIS ATRIBUTOS, e o motivo é de 03/09/2026: `desenho` deixou de ser
    # `data-papel` na bancada e virou `data-hef` — o ouvinte do piloto lê todo
    # `data-papel` como nome de GESTO, e `desenho` não tem quem atenda (ver
    # `aba05.PAPEIS_QUE_SAO_GESTO`). O que este guarda mede é se o ENDEREÇO
    # existe na página, e os dois atributos são endereço
    # (`regua_do_mockup.ATRIBUTOS_DE_CAMPO`). Cobrar só o antigo faria o
    # `--publicar 05` quebrar um teste que nada tem a ver com a mudança.
    for endereco in ("testar", "parar", "forca", "desenho"):
        assert (f'data-papel="{endereco}"' in doc
                or f'data-hef="{endereco}"' in doc), (
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
@pytest.mark.parametrize("pagina",  # (noqa-acento): nome do argumento
                         ["01-jogar.html", "02-controles.html",
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
def test_a_coluna_reservada_entra_na_uniao_das_chaves(pacotes_mod):
    """A LINHA QUE NENHUM LITERAL ALCANÇAVA, e é a que sustenta a cura inteira.

    O molde só vira travessão porque a conta soma a coluna `*` à união das
    chaves. Pular a chave reservada é o que qualquer pessoa faria ao "limpar" um
    dicionário de `p1..p4` com um `*` no meio — e é o que mata a cura sem
    encostar em nenhum dos três literais que a régua antiga cobrava. Medido em
    02/09/2026: com o `continue`, a régua do mockup volta ao
    `330 · 114 · 179 · 37` da mesa vazia e os 13 testes ficam verdes.

    Aqui a conta é RODADA, e a asserção é sobre o que ela produz.
    """
    molde = {"bateria": pacotes_mod.TRAVESSAO, "via": pacotes_mod.TRAVESSAO}
    carga = {"colunas": {pacotes_mod.LUGAR_SEM_DONO: dict(molde)}, "mesa": {}}
    pacotes_mod.apagar_os_lugares_sem_dono(carga)
    for pref in LUGARES:
        assert carga["colunas"][pref] == molde, (
            f"{pref} não recebeu as chaves do molde — a coluna reservada ficou "
            "de fora da união e a cura morreu inteira")
    assert sorted(carga["vazios"]) == sorted(LUGARES)


def test_a_coluna_viva_manda_e_o_lugar_dela_nao_e_apagado(pacotes_mod):
    """Quem tem dono não recebe travessão — e a união vem das colunas VIVAS."""
    carga = {"colunas": {"p1": {"bateria": "95%", "via": "USB"}}, "mesa": {}}
    pacotes_mod.apagar_os_lugares_sem_dono(carga)
    assert carga["colunas"]["p1"] == {"bateria": "95%", "via": "USB"}
    assert carga["vazios"] == ["p2", "p3", "p4"]
    assert set(carga["colunas"]["p2"].values()) == {pacotes_mod.TRAVESSAO}
    assert set(carga["colunas"]["p2"]) == {"bateria", "via"}


def test_o_piloto_ainda_chama_a_conta_do_despachante():
    """As duas pontas continuam ligadas — e agora o elo é uma CHAMADA.

    O ELO É A CHAMADA, E A CHAMADA SE LÊ NA ÁRVORE — 03/09/2026. Este teste
    digitava a assinatura inteira (`...sem_dono(carga)`) e reprovou no dia em que
    a função ganhou um segundo argumento: o piloto passou a escrever
    `apagar_os_lugares_sem_dono(carga, _com_dono(ctx))`, que é a cura de
    QUEM-TEM-DONO-01 — e a régua acusou a MELHORA de ter quebrado o elo. Foi
    achado por uma frente da leva de paridade, medindo numa árvore limpa para
    provar que o vermelho não era dela.

    *Régua que digita a assinatura envelhece na primeira melhora.* O que importa
    é que a chamada EXISTA, não quantos argumentos ela leva — e `ast` responde
    isso sem opinar sobre a forma.
    """
    import ast

    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    chamadas = [
        n for n in ast.walk(ast.parse(piloto))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "apagar_os_lugares_sem_dono"
    ]
    assert chamadas, (
        "o piloto deixou de CHAMAR `apagar_os_lugares_sem_dono` — o molde do "
        "despachante ficou sem quem o aplique, e as colunas sem dono voltam a "
        "mostrar o desenho")
    # E A CARGA CONTINUA SENDO O PRIMEIRO ARGUMENTO. Sem esta metade, alguém
    # poderia chamar a função com outra coisa e o teste ficaria verde sobre uma
    # chamada que não apaga a carga do tique.
    assert any(c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == "carga"
               for c in chamadas), (
        "a chamada existe mas não recebe a `carga` do tique como primeiro "
        "argumento — o molde aplicado seria outro")
