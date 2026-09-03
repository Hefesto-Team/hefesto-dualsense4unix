#!/usr/bin/env python3
"""A RÉGUA QUE DECIDE: com um DUBLÊ, nenhum campo da 06 pode ficar indecidível.

O BURACO QUE ELA FECHA, medido em 02/09/2026. A `--prova-de-mockup` classifica
cada campo da tela em três montes:

    PRODUTO      o valor mudou em relação ao cravado no arquivo publicado
    MOCKUP       igual ao cravado, e nenhum pacote declara este endereço
    INDECIDIVEL  igual ao cravado, e o pacote declara EXATAMENTE esse valor

A aba Navegação era **28 indecidíveis de 29 campos** — de longe a maior
concentração da casa. INDECIDÍVEL não é defeito: é o limite honesto de um
instrumento que lê a TELA. Se o desenho cravou `6` e o daemon dela diz `6`,
olhar a tela não separa *"pintou o valor certo"* de *"nunca pintou"*.

**A cura é fazer o valor MUDAR.** Esta régua troca o daemon por um DUBLÊ que
discorda do desenho em TODOS os endereços — quatro controles em vez de dois,
cada um com uma cor de plástico que não é a do desenho, o primário no segundo
lugar, a velocidade do cursor em 11, o teclado desligado e um `button_actions`
que troca as vinte e uma linhas — e então pergunta ao classificador da casa, sem
abrir janela:

    sob este dublê, algum campo ainda cai em INDECIDIVEL?

Um `INDECIDIVEL` aqui é a régua confessando que aquele endereço continua sem
decisão — e nomeia qual. Zero é a única saída aceitável.

O QUE ESTA RÉGUA **NÃO** PROVA, e ela diz: que a tela acompanhou. Isso é do
piloto, e foi medido em 02/09 com o mesmo dublê, pela `--prova-de-mockup` com a
fila reduzida à 06:

    mesa dela (2 controles)   produto  1 · mockup 0 · indecidível 28

Aqui fica a metade que roda no CI, sem GTK, sem display e sem daemon.

A PÁGINA ERA DE 29 ENDEREÇOS E É DE 38 — 03/09/2026, número substituído. A onda
IDENTIDADE-VEM-DE-CIMA acrescentou NOVE à `06-navegacao` publicada: os quatro
`plastico` da mesa, os dois `identidade` dos cartões, os dois `quem-navega` das
dicas e o `fita-chips` do topo. **Antes de mexer no número foi conferido o que a
mensagem da régua manda conferir** — que o dublê discorda dos 38, um a um: a
saída campo a campo está no dump que gerou esta correção, e os dois casos que
NÃO discordavam viraram o quarto controle e as quatro cores lidas.

A MORDIDA: faça o dublê concordar com o desenho em qualquer campo — troque
`speed` para 6, tire o `button_actions`, ou esvazie `CORES_LIDAS` — e a régua
nomeia o endereço que voltou a ser indecidível.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: QUATRO CONTROLES SINTÉTICOS, na faixa da casa — há dois portões de anonimato
#: nesta árvore e um endereço mascarado ainda carrega o OUI do aparelho dela.
#:
#: O `player_slot` NÃO É ENFEITE: é ele que ordena a mesa
#: (`mesa_viva._por_numero_de_identidade`), e sem ele a régua dependeria da
#: ordem de inserção — o dia em que a ordem mudasse, o `p1` cairia sobre o
#: mesmo valor que o desenho crava e o campo voltaria a INDECIDIVEL sem que
#: ninguém tivesse mexido no pacote.
#:
#: A MESA DO DUBLÊ DISCORDA DO DESENHO DE PROPÓSITO, campo a campo:
#:   · são QUATRO (o desenho crava "2 controles:" e "1 USB · 1 BT");
#:   · o `p1` está no RÁDIO e NÃO navega (o desenho crava "USB • Navega o PC");
#:   · o `p2` está no CABO e NAVEGA (o desenho crava "BT • Só a janela").
#:
#: ELES ERAM TRÊS ATÉ 03/09/2026, e o quarto entrou por medição. A onda
#: IDENTIDADE-VEM-DE-CIMA deu endereço aos QUATRO lugares da mesa
#: (`a06_navegacao`, o campo `plastico`, uma lista de 4), e o desenho tem dois
#: lugares VAZIOS. Com três controles, o quarto lugar recebia `""` e o desenho
#: também crava `""` — INDECIDIVEL para sempre, num endereço que ninguém pode
#: fazer variar de fora. O quarto controle é o que ocupa aquele lugar.
CONTROLES = [
    {"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "bt",
     "player_slot": 1, "is_primary": False},
    {"uniq": "02:fe:00:00:00:02", "connected": True, "transport": "usb",
     "player_slot": 2, "is_primary": True},
    {"uniq": "e8:47:3a:00:00:03", "connected": True, "transport": "usb",
     "player_slot": 3, "is_primary": False},
    {"uniq": "aa:bb:cc:00:00:04", "connected": True, "transport": "usb",
     "player_slot": 4, "is_primary": False},
]


class _CorLida:
    """O que `integrations.cor_do_plastico` devolve: um código e um nome.

    `mesa_viva.mesa_do_estado` lê os dois por `getattr`, e é do CÓDIGO que sai o
    `colorway` — a tradução é do CSV dela (`mesa_viva.CORES`), nunca digitada
    aqui. Por isso o dublê declara o código, e não o slug.
    """

    def __init__(self, codigo: str, nome: str) -> None:
        self.codigo = codigo  # (noqa-acento) nome de atributo do produto
        self.nome = nome


#: A COR DO PLÁSTICO QUE CADA UM RESPONDE — 03/09/2026, e ela é o que DECIDE os
#: quatro `plastico` da mesa. Nenhum destes quatro modelos é o do desenho: a
#: `06-navegacao` publicada crava Cosmic Red no `p1` e Starlight Blue no `p2`.
#:
#: SEM ISTO O DUBLÊ NÃO DISCORDA: um controle sem cor lida emite `""`, e `""` é
#: o que o desenho crava nos dois lugares vazios. Um dublê que cala onde o
#: desenho cala não decide nada — que é a definição de INDECIDIVEL desta régua.
CORES_LIDAS = {
    "aa:bb:cc:00:00:01": _CorLida("00", "White"),
    "02:fe:00:00:00:02": _CorLida("04", "Galactic Purple"),
    "e8:47:3a:00:00:03": _CorLida("09", "Cobalt Blue"),
    "aa:bb:cc:00:00:04": _CorLida("07", "Volcanic Red"),
}

#: O estado do daemon, escolhido para DISCORDAR do desenho em cada número:
#: o cursor vai a 11 (o desenho crava 6), a rolagem a 4 (crava 1) e o teclado
#: sai DESLIGADO (crava "Ligada — atalhos e teclado na tela").
ESTADO = {
    "active_profile": "Dublê da Navegação",
    "mouse_emulation": {"enabled": True, "speed": 11, "scroll_speed": 4,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": False, "osk_disponivel": False},
    "controllers": CONTROLES,
}


def _button_actions() -> dict[str, str]:
    """Uma escolha DIFERENTE do de fábrica para cada uma das 21 linhas.

    O vocabulário é o do motor (`core.acoes_de_botao`), inteiro: as linhas que
    existem, o que cada uma faz de fábrica e a lista de opções saem de lá. Este
    dublê não digita rótulo nenhum — ele só escolhe, para cada botão, o
    primeiro token que NÃO é o de fábrica daquela linha.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    de_fabrica = acoes.padrao()
    fora: dict[str, str] = {}
    for botao in acoes.BOTOES:
        for token in acoes.ACOES:
            if token != de_fabrica.get(botao):
                fora[botao] = token
                break
    return fora


PERFIL = {"name": "Dublê da Navegação", "button_actions": _button_actions(),
          "key_bindings": {"l1": ["KEY_F11"]}}


def _no_mundo_de(monkeypatch, publicado: bool):
    """`(cravados, declarados)` NA PÁGINA QUE ESTIVER CARREGADA.

    Os dois lados saem de quem já é dono deles: os cravados de
    `regua_do_mockup._campos_cravados` (o mesmo parser que a `--prova-de-mockup`
    usa) e os declarados de `regua_do_mockup._declarados_do_pacote` sobre a
    carga NORMALIZADA — isto é, exatamente o que iria para a tela naquele tique,
    cabeçalho incluído. Ler o código-fonte do pacote em vez da carga seria
    perguntar se o NOME do campo aparece, que é o erro que produziu o "77%".

    `publicado` É O MUNDO — 02/09/2026, corretivo. `True` é a página que o
    piloto carrega hoje; `False` é a bancada, que vira a tela dela no dia em que
    ela publicar. A "Função do teclado" fala a língua da página carregada
    (`a06_navegacao.PALAVRAS_DO_TECLADO`), então medir num mundo só deixaria o
    outro quebrar calado — que foi exatamente o que aconteceu.
    """
    import pacotes
    from pacotes import a06_navegacao, perfil

    from hefesto_dualsense4unix.interface import mesa_viva, onde, regua_do_mockup

    monkeypatch.setattr(perfil, "ativo", lambda nome: dict(PERFIL) if nome else {})
    monkeypatch.setattr(
        a06_navegacao, "_o_que_a_pagina_oferece",
        lambda: frozenset(_opcoes_da_pagina(publicado, "teclado-estado") or ()))

    mesa = mesa_viva.mesa_do_estado(ESTADO, CORES_LIDAS)
    ctx = pacotes.Contexto(state=ESTADO, mesa=mesa, conectados=CONTROLES, estados={})
    carga = pacotes.normalizar(a06_navegacao.pacote(ctx),
                               {str(c["uniq"]): c["pref"] for c in mesa})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)

    texto = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    return regua_do_mockup._campos_cravados(texto), \
        regua_do_mockup._declarados_do_pacote(carga)


@pytest.fixture
def sob_o_duble(monkeypatch):
    """O mundo de HOJE: a página que o piloto carrega (`publicado=True`)."""
    return _no_mundo_de(monkeypatch, publicado=True)


def test_o_duble_nao_deixa_um_campo_indecidivel(sob_o_duble):
    """Nenhum dos 38 endereços pode concordar com o desenho sob este dublê.

    A tela dos `vivos` é o CRAVADO — isto é, a régua pergunta *"e se a pintura
    não tivesse acontecido?"*. Sob um dublê que discorda do desenho, todo campo
    tem de cair em `MOCKUP` com a nota de endereço morto; um `INDECIDIVEL` aqui
    quer dizer que o pacote declarou o MESMO valor que o desenho crava — e esse
    campo continua sem decisão na régua viva, para sempre.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vereditos = r._classificar(cravados, [c.valor for c in cravados], declarados)
    parados = [f"{v.campo.endereco} = {v.campo.valor!r}"
               for v in vereditos if v.classe == r.INDECIDIVEL]
    assert not parados, (
        "estes endereços da 06 concordam com o desenho ATÉ SOB O DUBLÊ, logo "
        "continuam indecidíveis na régua viva:\n  " + "\n  ".join(parados)
        + "\nOu o pacote não varia esse campo com o estado, ou o dublê acima "
          "escolheu por acaso o mesmo valor que o desenho crava — nos dois "
          "casos ler a tela não decide nada sobre ele.")


def test_o_duble_cobre_os_vinte_e_nove_enderecos(sob_o_duble):
    """Endereço sem dono nenhum é a outra metade — e não pode existir aqui.

    `MOCKUP` sem valor declarado é *"nenhum pacote declara este endereço"*, que
    é diferente de endereço morto: é campo órfão. A 06 não tem nenhum, e esta
    linha impede que ganhe um em silêncio.

    O NOME DESTA FUNÇÃO CONGELOU O 29 — 03/09/2026, e a página tem 38. O número
    certo está na linha abaixo e no cabeçalho do arquivo, com o que foi
    conferido antes de trocá-lo; o nome do nó ficou porque a leva de hoje o
    persegue por id. **Quem passar aqui depois: renomeie para
    `test_o_duble_cobre_os_enderecos_da_pagina`** — sem número no nome, que é o
    único que não envelhece.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vereditos = r._classificar(cravados, [c.valor for c in cravados], declarados)
    orfaos = [v.campo.endereco for v in vereditos if v.declarado is None]
    assert not orfaos, (
        f"{orfaos} existe(m) na página publicada e pacote nenhum os declara — "
        "a tela mostra o desenho e ninguém acusa.")
    assert len(cravados) == 38, (
        f"a página publicada tem {len(cravados)} endereços de campo; esta régua "
        "foi escrita sobre 38. Se o desenho mudou, confira se o dublê acima "
        "ainda discorda de TODOS eles antes de mexer neste número.")


def test_quando_a_tela_acompanha_tudo_vira_produto(sob_o_duble):
    """O outro lado da mesma moeda: se a pintura pousar, os 38 saem PRODUTO.

    Aqui os `vivos` são o que o `escrever()` do bootstrap poria na tela para o
    valor declarado — a mesma tradução que a `--prova-de-mockup` usa —, e o
    veredito tem de ser PRODUTO em todos. É a metade que fecha o número que a
    régua viva publica.

    FATO SUBSTITUÍDO — 02/09/2026, corretivo. Este docstring justificava a
    própria existência assim: *"sem esta metade a régua acima passaria com um
    pacote que emitisse lixo"*. **Ela passa com lixo do mesmo jeito**, e a
    medição é de um comando — o mesmo dublê com TODO valor declarado trocado
    por `'LIXO — ISTO NÃO É DADO'`:

        declarado CERTO  · teste1 INDECIDIVEL=[] · teste3 {PRODUTO 29, 0, 0}
        declarado LIXO   · teste1 INDECIDIVEL=[] · teste3 {PRODUTO 29, 0, 0}

    Os dois vereditos são IDÊNTICOS porque as duas metades reduzem ao MESMO
    predicado — `_como_a_tela_escreveria(declarado) != cravado`
    (`regua_do_mockup._classificar`). Uma passa `vivos = cravados` e a outra
    `vivos = declarado`, e nos dois casos o que decide é a mesma comparação.

    **Quem separa "pintar certo" de "escrever lixo" são as DUAS linhas
    abaixo**, e nenhuma delas é esta: `test_todo_valor_do_duble_existe_como_opcao`
    para os 22 `<select>`, e `test_os_sete_campos_de_texto_dizem_o_que_o_duble_diz`
    para os outros sete — que até hoje não tinham guarda nenhuma.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vivos = [r._como_a_tela_escreveria(
        declarados.get((c.dono, c.chave), declarados.get(("", c.chave))))
        for c in cravados]
    vereditos = r._classificar(cravados, vivos, declarados)
    contas = r._contar(vereditos)
    # A QUARTA CONTA (`ROTULO`) entrou em 03/09/2026, com a decisão dela: um
    # título de seção é texto fixo, não é dado que o produto escreva. A 06 não
    # tem nenhum marcado, e o zero aqui é o que impede um campo de virar rótulo
    # em silêncio para sair da dívida.
    assert contas == {r.PRODUTO: 38, r.ROTULO: 0, r.MOCKUP: 0,
                      r.INDECIDIVEL: 0}, (
        f"com a tela acompanhando o dublê a régua diz {contas}, e o esperado é "
        "38 PRODUTO. Um campo fora disso é o pacote emitindo o valor do desenho.")


#: A REGRA DO `escrever()` PARA `data-hef-alvo="valor"`, e ela é do PILOTO:
#: um `<select>` só aceita o texto exato de uma `<option>` — fora disso a
#: pintura devolve `0` **em silêncio** (`hefesto_vivo.BOOTSTRAP`, ramo
#: `alvo === 'valor'`). Um valor que não casa é um campo que nunca anda, sem uma
#: linha de erro em lugar nenhum.
_SELECT = r'<select[^>]*data-campo="{}"[^>]*>(.*?)</select>'

#: OS DOIS MUNDOS QUE ESTA RÉGUA ATRAVESSA — 02/09/2026, corretivo.
#:
#: O desenho anda na BANCADA e o produto só recebe quando ela publica
#: (`scripts/check_o_desenho_aprovado.py --publicar`). Nesse intervalo há DUAS
#: telas possíveis, e a régua tem de valer nas duas — a de hoje, que é a que ela
#: clica, e a de depois, que é a que a publicação entrega.
#:
#: A VERSÃO ANTERIOR DESTA LINHA ERA UMA DECLARAÇÃO — `ESPERANDO_A_PUBLICACAO =
#: {"teclado-estado"}` — e ela olhava para a coisa errada. Declarava que o campo
#: PARARIA de ser pintado até a publicação, e o que aconteceu foi pior: o campo
#: continuou sendo pintado **com a palavra errada**, e a tela passou a afirmar
#: `Ligada — atalhos e teclado na tela` com o teclado DESLIGADO. Uma declaração
#: não conserta tela; ela só documenta o estrago.
#:
#: O QUE FICOU NO LUGAR: o pacote fala a língua da página CARREGADA
#: (`a06_navegacao.PALAVRAS_DO_TECLADO`), e a régua roda nos dois mundos
#: cobrando casamento OBRIGATÓRIO em cada um. Não há mais nada a declarar —
#: publicar deixou de ser uma dívida da tela e voltou a ser só a troca do
#: desenho.
OS_DOIS_MUNDOS = [
    pytest.param(True, id="a-pagina-publicada-de-hoje"),
    pytest.param(False, id="a-bancada-do-dia-da-publicacao"),
]


def _opcoes_da_pagina(publicado: bool, chave: str) -> set[str] | None:
    """As `<option>` daquele `<select>`, na bancada ou no publicado."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_SELECT.format(re.escape(chave)), doc, re.S)
    if not bloco:
        return None
    return set(re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1)))


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_todo_valor_do_duble_existe_como_opcao(monkeypatch, publicado):
    """As 22 escolhas do dublê têm de ser oferecidas pela lista daquela linha.

    O teste irmão (`test_a_06_nao_manda_para_o_vazio`) cobre isto para o
    **de fábrica**; aqui o alvo são as opções que só aparecem quando o perfil
    dela diverge — que é justamente o caso que nunca foi exercitado, e o que
    faria um campo ficar parado para sempre sem ninguém ver.

    NOS DOIS MUNDOS, E OBRIGATÓRIO NOS DOIS — 02/09/2026, corretivo. Cada volta
    carrega uma das duas páginas e cobra o mesmo: todo valor que o pacote
    escreveria naquela tela existe como `<option>` DELA. A página publicada é a
    que ela clica hoje; a bancada é a que a publicação entrega. Um pacote que só
    soubesse falar com uma delas quebraria a outra em silêncio — e foi assim
    que a tela passou a dizer `Ligada — atalhos e teclado na tela` com o teclado
    desligado.

    A MORDIDA: crave a palavra da bancada na pintura (`mesa["teclado-estado"] =
    TECLADO_SO_FORA if … else TECLADO_DESATIVADO`) — a volta
    `a-pagina-publicada-de-hoje` reprova nomeando o valor que a lista dela não
    oferece.
    """
    cravados, declarados = _no_mundo_de(monkeypatch, publicado)
    onde_estou = "publicada" if publicado else "da bancada"
    conferidos = 0
    for campo in cravados:
        if campo.alvo != "valor":
            continue
        valor = str(declarados.get((campo.dono, campo.chave),
                                   declarados.get(("", campo.chave))))
        oferece = _opcoes_da_pagina(publicado, campo.chave)
        assert oferece is not None, (
            f"{campo.endereco}: a página {onde_estou} não tem `<select>` com "
            "esse endereço")
        assert valor in oferece, (
            f"{campo.endereco}: na página {onde_estou} o dublê manda {valor!r} "
            f"e a lista oferece {sorted(oferece)} — o `escrever()` devolveria 0 "
            "em silêncio, e o que ficaria na tela é a `<option selected>` que o "
            "desenho crava. O campo não para: ele passa a AFIRMAR o contrário.")
        conferidos += 1
    assert conferidos == 22, (
        f"conferi {conferidos} listas na página {onde_estou} e a aba tem 22 (as "
        "21 linhas de botão mais a 'Função do teclado') — se o número caiu, um "
        "`<select>` perdeu o endereço e saiu da conferência sem reprovar nada.")


def test_os_sete_campos_de_texto_dizem_o_que_o_duble_diz(sob_o_duble):
    """Os 14 campos que NÃO são `<select>` têm de dizer o que o dublê mandou.

    O BURACO QUE ELA FECHA, medido em 02/09/2026 (corretivo). As duas metades
    acima reduzem ao mesmo predicado — *o declarado é diferente do cravado* — e
    LIXO também é diferente: com todo valor trocado por `'LIXO — ISTO NÃO É DADO'` as
    duas passam, com o mesmo veredito de sempre. Quem pegava lixo era só
    `test_todo_valor_do_duble_existe_como_opcao`, e só para os 22 `<select>`.

    ERAM SETE E SÃO CATORZE — 03/09/2026, número substituído, e o NOME desta
    função congelou o sete. Os outros sete chegaram com a onda
    IDENTIDADE-VEM-DE-CIMA e **todos ganharam linha aqui**, que é o que esta
    régua existe para exigir: `fita-chips`, `p1·identidade`, `p2·identidade`,
    `quem-navega` e os três endereços de `plastico` (os dois cartões e os dois
    lugares vazios compartilham a mesma lista de quatro cores). Subir o número
    sem escrever a guarda teria deixado sete campos sem defesa contra valor
    destruidor — o oposto do que a linha do número diz.

    O QUE ELA COBRA, e a distinção é a razão de ela existir: **o esperado sai do
    DUBLÊ, não do pacote**. Nada aqui chama `a06_navegacao` para descobrir a
    resposta — a contagem sai de `CONTROLES`, os números saem de `ESTADO`, o par
    via/papel de cada cartão sai do `transport`/`is_primary`, e a cor e o nome de
    cada modelo saem de `CORES_LIDAS` traduzidas pelos donos do dado
    (`mesa_viva.CORES`, que é o CSV dela, e `monta.cor_da_zona`, que lê o SVG).
    Uma régua que perguntasse ao pacote o que esperar do pacote é a forma de
    instrumento falso que esta casa mais achou.

    A MORDIDA: troque `speed` do dublê para 6, faça o pacote emitir qualquer
    outra coisa em `vel-cursor`, ou devolva a cor do mockup ao `plastico` — esta
    linha reprova nomeando o endereço.
    """
    import monta

    from hefesto_dualsense4unix.interface import mesa_viva

    cravados, declarados = sob_o_duble
    valor = {c.endereco: declarados.get((c.dono, c.chave),
                                        declarados.get(("", c.chave)))
             for c in cravados if c.alvo != "valor"}
    assert len(valor) == 14, (
        f"a página tem {len(valor)} campos fora dos `<select>` e esta régua foi "
        "escrita sobre 14. Um campo novo sem linha aqui é um campo sem guarda "
        "contra valor destruidor.")

    ligados = [c for c in CONTROLES if c.get("connected")]
    usb = sum(1 for c in ligados if c.get("transport") == "usb")
    bt = len(ligados) - usb
    rato = ESTADO["mouse_emulation"]
    conta_b = str(valor["conta-b"])

    assert str(len(ligados)) in str(valor["conta"]), (
        f"o dublê tem {len(ligados)} controles ligados e o cabeçalho diz "
        f"{valor['conta']!r}")
    assert f"{usb} USB" in conta_b and f"{bt} BT" in conta_b, (
        f"o dublê tem {usb} no cabo e {bt} no rádio, e a segunda metade do "
        f"cabeçalho diz {conta_b!r}")
    assert valor["perfil"] == ESTADO["active_profile"], (
        f"o perfil ativo do dublê é {ESTADO['active_profile']!r} e a tela "
        f"receberia {valor['perfil']!r}")
    assert str(valor["vel-cursor"]) == str(rato["speed"]), (
        f"o dublê manda `speed={rato['speed']}` e o campo diz "
        f"{valor['vel-cursor']!r}")
    assert str(valor["vel-rolagem"]) == str(rato["scroll_speed"]), (
        f"o dublê manda `scroll_speed={rato['scroll_speed']}` e o campo diz "
        f"{valor['vel-rolagem']!r}")

    # OS DOIS CARTÕES. Quem diz qual controle caiu em `p1` é a mesa do produto
    # (`mesa_viva`, dona da ordem); o que ele É — cabo ou rádio, primário ou não
    # — sai do dublê, e é contra isso que a linha do cartão é conferida.
    por_uniq = {str(c["uniq"]): c for c in CONTROLES}
    mesa = mesa_viva.mesa_do_estado(ESTADO, CORES_LIDAS)
    conferidos = 0
    for lugar in mesa:
        endereco = f"{lugar['pref']}·navega"
        if endereco not in valor:
            continue  # o desenho só tem dois cartões; o terceiro não aparece
        c = por_uniq[str(lugar["uniq"])]
        via = "USB" if c.get("transport") == "usb" else "BT"
        papel = "Navega o PC" if c.get("is_primary") else "Só a janela"
        linha = str(valor[endereco])
        assert via in linha and papel in linha, (
            f"{endereco}: o dublê pôs neste lugar um controle no {via} que "
            f"{papel.lower()}, e a linha do cartão diz {linha!r}")
        conferidos += 1
    assert conferidos == 2, (
        f"conferi {conferidos} cartões e o desenho tem 2 — se o número caiu, um "
        "cartão perdeu o endereço e saiu da conferência sem reprovar nada.")

    # -----------------------------------------------------------------------
    # OS SETE QUE A ONDA IDENTIDADE-VEM-DE-CIMA TROUXE
    #
    # O ESPERADO DE CADA UM SAI DO DUBLÊ, traduzido pelos donos do dado: o
    # código de fábrica de `CORES_LIDAS` vira slug e nome em `mesa_viva.CORES`
    # (o CSV dela), e o slug vira hexadecimal em `monta.cor_da_zona` (que lê o
    # `<style>` do SVG). Digitar `#e4e0d8` aqui seria a segunda verdade que o
    # portão `check_cores_do_dualsense.py` existe para matar.
    # -----------------------------------------------------------------------
    modelo = {}   # pref -> nome do modelo que aquele lugar tem de anunciar
    hexes = []    # a cor de cada lugar, na ordem da mesa
    for lugar in mesa:
        slug, nome = mesa_viva.CORES[CORES_LIDAS[str(lugar["uniq"])].codigo]
        modelo[str(lugar["pref"])] = nome
        hexes.append(monta.cor_da_zona(slug))

    # A COR DO PLÁSTICO É UMA LISTA SÓ, e os três endereços de `plastico` a
    # compartilham: o pacote emite `mesa["plastico"]` com um valor por lugar, e
    # o piloto a distribui pelos elementos de mesmo endereço, na ordem.
    for endereco in ("p1·plastico", "p2·plastico", "plastico"):
        assert list(valor[endereco]) == hexes, (
            f"{endereco}: o dublê lê {[c.codigo for c in CORES_LIDAS.values()]} "
            f"nos quatro lugares, o que dá {hexes}, e o campo diz "
            f"{valor[endereco]!r}")

    # O NOME DO MODELO, no cartão de cada um dos dois lugares que o desenho tem.
    for pref, nome in modelo.items():
        endereco = f"{pref}·identidade"
        if endereco not in valor:
            continue
        assert str(valor[endereco]) == nome, (
            f"{endereco}: o aparelho daquele lugar é um {nome} e o cartão diz "
            f"{valor[endereco]!r} — a identidade voltou a vir do desenho")

    # QUEM NAVEGA O PC é o primário, e a dica das duas telas de botão o nomeia.
    # É o campo que diz para quem valem as 21 linhas: errar aqui é oferecer o
    # ajuste de um controle e aplicá-lo noutro.
    primario = [lugar for lugar in mesa
                if por_uniq[str(lugar["uniq"])].get("is_primary")]
    assert len(primario) == 1, f"o dublê tem {len(primario)} primários"
    lugar = primario[0]
    c = por_uniq[str(lugar["uniq"])]
    dica = str(valor["quem-navega"])
    for pedaco in (str(lugar["pref"]).upper(), modelo[str(lugar["pref"])],
                   "USB" if c.get("transport") == "usb" else "BT"):
        assert pedaco in dica, (
            f"quem-navega: o primário do dublê é o {lugar['pref']} "
            f"({modelo[str(lugar['pref'])]}), e a dica diz {dica!r} — falta "
            f"{pedaco!r}")

    # A FITA DO TOPO — um chip por controle DA MESA, mais o "Todos". Ela é o que
    # ela olha para saber quem está ligado; mostrar o controle do desenho aqui é
    # o defeito que já apareceu quatro vezes nesta casa.
    fita = str(valor["fita-chips"])
    quantos = fita.count('class="chip')
    assert quantos == len(mesa) + 1, (
        f"a mesa do dublê tem {len(mesa)} controles e a fita traz {quantos} "
        f"chips (contando o 'Todos'): {fita!r}")
    for lugar in mesa:
        assert str(lugar["pref"]).upper() in fita, (
            f"a fita não traz o chip do {lugar['pref']}: {fita!r}")
        assert modelo[str(lugar["pref"])] in fita, (
            f"a fita não nomeia o {modelo[str(lugar['pref'])]} do "
            f"{lugar['pref']}: {fita!r}")
