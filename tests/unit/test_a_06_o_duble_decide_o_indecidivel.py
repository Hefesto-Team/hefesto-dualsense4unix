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

A PÁGINA CRESCE, E OS NÚMEROS DESTE ARQUIVO SÃO LIDOS DELA — 29, depois 38,
depois 43 com a publicação das dez. As três asserções que digitavam o número
caíram no mesmo dia (03/09/2026) e viraram piso + comparação de conjuntos. A onda
IDENTIDADE-VEM-DE-CIMA acrescentou NOVE à `06-navegacao` publicada: os quatro
`plastico` da mesa, os dois `identidade` dos cartões, os dois `quem-navega` das
dicas e o `fita-chips` do topo. **Antes de mexer no número foi conferido o que a
mensagem da régua manda conferir** — que o dublê discorda de TODOS, um a um: a
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


#: CRAVAR VAZIO NÃO É CRAVAR — 03/09/2026, e é a correção de um erro de
#: enquadramento desta régua. Ela exigia que o dublê DISCORDASSE de todo campo
#: cravado, e dois endereços da 06 (`rato-estado`, `teclado-bloqueio`) nascem
#: como `<div class="estado">` sem conteúdo nenhum. Sob o dublê eles também
#: davam `''`, e a régua os chamava de indecidíveis.
#:
#: Só que **o desenho não afirma nada sobre eles**. "Indecidível" quer dizer
#: *não dá para saber se a tela mostra dado ou mostra o desenho*; onde o desenho
#: é vazio não há a segunda hipótese. O campo é do produto por construção — e os
#: dois têm dono declarado (`a06_navegacao:1033-1034`).
#:
#: A EXCLUSÃO NÃO É UMA LISTA DE NOMES, e isso importa: é uma REGRA sobre o
#: valor. Uma lista envelheceria no primeiro endereço vazio novo, e alguém teria
#: de vir aqui escrevê-lo — que é o defeito de digitar o que se pode ler.
def _cravados_que_afirmam(cravados):
    """Só os campos sobre os quais o desenho DIZ alguma coisa.

    `_campos_cravados` devolve uma LISTA de `_Campo`, e o valor mora em
    `.valor` — não é um dicionário. Tratá-la como mapa foi o primeiro tropeço
    desta correção, e o erro apareceu na hora: `'list' object has no attribute
    'items'`.
    """
    return [c for c in cravados if str(c.valor).strip()]


@pytest.fixture
def sob_o_duble(monkeypatch):
    """O mundo de HOJE: a página que o piloto carrega (`publicado=True`)."""
    cravados, declarados = _no_mundo_de(monkeypatch, publicado=True)
    return _cravados_que_afirmam(cravados), declarados


def test_o_duble_nao_deixa_um_campo_indecidivel(sob_o_duble):
    """Nenhum endereço que o desenho AFIRMA pode concordar com ele sob o dublê.

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


#: A BARRA NÃO É UMA LISTA, e a régua acima só sabia perguntar a listas.
#: Nasceu em 05/09/2026, com a decisão dela — *"velocidade do cursor e da
#: rolagem coloca um slicer pra cada"*: as duas linhas deixaram de ser um
#: `<select>` e viraram `<input type="range">`, e a régua passou a reprovar
#: dizendo *"a página não tem `<select>` com esse endereço"* — verdade, e
#: irrelevante. Afrouxá-la (pular todo campo sem `<select>`) teria deixado de
#: medir DUAS linhas em que o dublê pode mandar número fora da faixa, que é o
#: mesmo defeito com outro nome. Ela aprendeu a perguntar à faixa.
_TRILHO = r'<input[^>]*type="range"[^>]*data-campo="{}"[^>]*>'


#: O CAMPO DE TEXTO É O TERCEIRO, e a régua acima só sabia perguntar a listas e
#: a barras. Nasceu em 06/09/2026, com a `NAVEGACAO-TECLAS-01`: a tela
#: "Teclas do teclado" tem oito `<input type="text">` com `data-hef-alvo="valor"`,
#: e ali **qualquer string cabe** — o `escrever()` do piloto faz `el.value = t`
#: sem lista a consultar e sem faixa a aparar. A pergunta que sobra é a que a
#: régua já fazia às outras duas formas: *este endereço EXISTE na página?*
#:
#: AFROUXAR SERIA PULAR TODO CAMPO SEM `<select>`, e é justamente o que a nota
#: da barra logo acima recusa: deixaria de medir os oito endereços em que o
#: dublê pode mandar valor para o vazio.
_TEXTO = r'<input[^>]*type="text"[^>]*data-campo="{}"[^>]*>'


def _e_campo_de_texto(publicado: bool, chave: str) -> bool:
    """A página tem um `<input type=text>` com esse endereço?"""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    return re.search(_TEXTO.format(re.escape(chave)), doc) is not None


def _faixa_da_pagina(publicado: bool, chave: str) -> tuple[int, int] | None:
    """O `min`/`max` daquele `<input type=range>`, ou ``None`` se não é barra."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_TRILHO.format(re.escape(chave)), doc)
    if not bloco:
        return None
    tag = bloco.group(0)
    minimo = re.search(r'\bmin="(-?\d+)"', tag)
    maximo = re.search(r'\bmax="(-?\d+)"', tag)
    if not minimo or not maximo:
        return None
    return int(minimo.group(1)), int(maximo.group(1))


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
        faixa = _faixa_da_pagina(publicado, campo.chave)
        if faixa is not None:
            # A LINHA É UMA BARRA: a pergunta muda de "está na lista?" para
            # "cabe na faixa?", e o estrago que ela evita é o mesmo — um número
            # fora do `min`/`max` faz o `<input>` aparar em silêncio, e o que
            # fica na tela deixa de ser o que o pacote disse.
            minimo, maximo = faixa
            assert minimo <= int(valor) <= maximo, (
                f"{campo.endereco}: na página {onde_estou} o dublê manda "
                f"{valor!r} e a barra vai de {minimo} a {maximo} — o navegador "
                "apara sem dizer nada, e a tela passa a AFIRMAR outro número.")
            conferidos += 1
            continue
        if _e_campo_de_texto(publicado, campo.chave):
            # O CAMPO DE TEXTO ACEITA QUALQUER STRING — não há lista a
            # consultar nem faixa a aparar: o `escrever()` do piloto faz
            # `el.value = t` direto. O que se confere aqui é que o endereço
            # EXISTE naquela página, que é a metade que valia para as outras
            # duas formas também.
            conferidos += 1
            continue
        oferece = _opcoes_da_pagina(publicado, campo.chave)
        assert oferece is not None, (
            f"{campo.endereco}: a página {onde_estou} não tem `<select>`, "
            "`<input type=range>` nem `<input type=text>` com esse endereço")
        assert valor in oferece, (
            f"{campo.endereco}: na página {onde_estou} o dublê manda {valor!r} "
            f"e a lista oferece {sorted(oferece)} — o `escrever()` devolveria 0 "
            "em silêncio, e o que ficaria na tela é a `<option selected>` que o "
            "desenho crava. O campo não para: ele passa a AFIRMAR o contrário.")
        conferidos += 1
    # O NÚMERO DEIXOU DE SER DIGITADO — 06/09/2026. Estava `== 24`, com a conta
    # escrita ao lado ("as 21 linhas de botão, a 'Função do teclado' e as DUAS
    # barras"). Quando o botão PS entrou na lista do produto (ONDA5-06-01/02) a
    # conta virou 25 e a régua reprovou a MELHORA, que é a forma exata do
    # defeito que esta casa já pagou onze vezes em 26/08. Agora ela PERGUNTA ao
    # dono da lista e soma os três campos que não são linha de botão.
    # E ELE PASSOU A CONTAR OS DOIS MUNDOS SEPARADAMENTE — 06/09/2026,
    # NAVEGACAO-TECLAS-01. A tela "Teclas do teclado" está na BANCADA e ainda
    # não no publicado (`mockup/DIVERGENCIAS.md`), então os oito campos de texto
    # existem numa página e não na outra. Um número só para as duas voltas
    # reprovaria a bancada por ter a tela nova, ou absolveria o publicado por
    # não ter — as duas leituras erradas.
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES, DOMINIO_DO_TECLADO

    com_tecla = sum(1 for b in sorted(DOMINIO_DO_TECLADO)
                    if _e_campo_de_texto(publicado, f"tecla-{b}"))
    assert com_tecla in (0, len(DOMINIO_DO_TECLADO)), (
        f"a página {onde_estou} tem {com_tecla} dos {len(DOMINIO_DO_TECLADO)} "
        "campos de tecla — meia tela é pior que nenhuma: o Guardar dela grava "
        "só o que achou e cala sobre o resto.")
    esperados = len(BOTOES) + 3 + com_tecla
    assert conferidos == esperados, (
        f"conferi {conferidos} linhas na página {onde_estou} e a aba tem "
        f"{esperados} (as {len(BOTOES)} linhas de botão, a 'Função do teclado', "
        f"as DUAS barras de velocidade e {com_tecla} campo(s) de tecla) — se o "
        "número caiu, uma linha perdeu o endereço e saiu da conferência sem "
        "reprovar nada.")


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
    # A CONTAGEM DEIXOU DE SER UM LITERAL — 03/09/2026. Esta linha dizia `== 14`
    # e a publicação das dez levou a página a 17 campos fora dos `<select>`: a
    # régua reprovou por haver MAIS tela endereçada, que é o contrário do que
    # ela existe para pegar. Foi a terceira asserção deste arquivo a cair pelo
    # mesmo motivo no mesmo dia — um número digitado sobre um arquivo que o
    # gerador escreve é uma segunda verdade, e ela sempre perde.
    #
    # O QUE A TRAVA GUARDA continua guardado, e agora sem envelhecer: os campos
    # NOMEADOS abaixo têm de existir. Um endereço novo entra sem quebrar nada;
    # um endereço que SOME reprova, porque a linha que o confere não o acha.
    assert len(valor) >= 14, (
        f"a página caiu para {len(valor)} campos fora dos `<select>`, e esta "
        "régua confere 14 nominalmente. Se um endereço sumiu, ele perdeu a "
        "guarda contra valor destruidor — confira antes de baixar este piso.")

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
    from hefesto_dualsense4unix.app.actions import home_actions

    mesa = mesa_viva.mesa_do_estado(ESTADO, CORES_LIDAS)
    conferidos = 0
    for lugar in mesa:
        endereco = f"{lugar['pref']}·navega"
        if endereco not in valor:
            continue  # o desenho só tem dois cartões; o terceiro não aparece
        c = por_uniq[str(lugar["uniq"])]
        # A PALAVRA DO TRANSPORTE É DO DONO, e ela MUDOU — 06/09/2026, com o
        # glossário da casa (`docs/A-LINGUA-DESTA-CASA…`): a tela passou a dizer
        # **cabo** e **rádio** onde dizia `USB` e `BT`. Esta linha digitava as
        # duas siglas e reprovou a MELHORA: o cartão dizia `rádio • Só a janela`
        # e a régua cobrava `BT`. Quem responde é
        # `home_actions.palavra_do_transporte`, o mesmo dono que a mesa consulta
        # — e no dia seguinte a uma troca de palavra a régua acompanha sozinha.
        via = home_actions.palavra_do_transporte(c.get("transport"))
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
    # OS ENDEREÇOS SÃO DESCOBERTOS, e não digitados — 03/09/2026. A lista era
    # `("p1·plastico", "p2·plastico", "plastico")`: dois com dono e um solto,
    # que era o par de lugares VAZIOS compartilhando um endereço sem dono.
    #
    # A cura de 03/09 deu `data-controle` aos lugares vazios das sete abas (a
    # decisão dela: *"se isso não ocorre com os 4 controles em cada aba, então
    # temos que construir isso e garantir isso"*), e o endereço solto virou
    # `p3·plastico` e `p4·plastico`. Medido no DOM VIVO depois da cura: os
    # QUATRO elementos recebem pintura (`data-hef-visto="1"`) e as cores estão
    # certas — p1 no branco lido do aparelho, os três vazios no neutro. A
    # distribuição por ordem não quebrou; o que quebrou foi a lista digitada.
    de_plastico = sorted(e for e in valor if e.endswith("plastico"))
    # O PISO É DOIS, e o motivo fecha o raciocínio acima: `_cravados_que_afirmam`
    # tira os campos que o desenho deixa VAZIOS, e o desenho não crava cor
    # nenhuma nos lugares desconectados — eles nascem no neutro da folha. Então
    # os endereços que chegam aqui são os dos lugares que o desenho PINTA.
    # Exigir quatro seria cobrar do desenho uma afirmação que ele não faz.
    assert len(de_plastico) >= 2, (
        f"a página tem {len(de_plastico)} endereço(s) de `plastico` que o "
        "desenho afirma, e a régua confere a cor de cada lugar por eles — se "
        f"sumiram, a cor do aparelho deixou de ser conferida: {de_plastico}")
    for endereco in de_plastico:
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
    # A MESMA TROCA DE PALAVRA da linha do cartão, e pelo MESMO dono: `cabo` e
    # `rádio` no lugar de `USB` e `BT` (glossário da casa, 06/09/2026).
    for pedaco in (str(lugar["pref"]).upper(), modelo[str(lugar["pref"])],
                   home_actions.palavra_do_transporte(c.get("transport"))):
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
