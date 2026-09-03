#!/usr/bin/env python3
"""O DESENHO dos cartões da aba Lançadores — um só, para o gerador e o pacote.

POR QUE ELE EXISTE, e a razão é a cicatriz mais cara desta casa: o gerador
`aba07.py` escrevia os seis cartões com os números DIGITADOS (`412 jogos`,
`28 jogos`, `3 jogos já sabem por onde entrar`) e o produto não tinha por onde
contradizê-los. Medido em 02/09/2026 na máquina dela, com o `censo_do_wrapper`:

    o HTML afirmava   Steam · 412 jogos · 3 já sabem por onde entrar
    o produto responde  63 appids com o wrapper no vdf, 23 jogos instalados,
                        0 faltantes, 0 com ponte confirmada

Quatro números, quatro contradições. É a forma exata do defeito que ela mediu
ao abrir o produto: *"basicamente todas as telas são mockups e estão com
informações incorretas ou desatualizadas ou não integradas de fato."*
<!-- noqa-acento: citação literal dela -->

A CURA NÃO É APAGAR O DESENHO — é dar-lhe UMA fonte. Este módulo é o desenho;
quem passa o dado é que muda:

    aba07.py (gerador)  →  a lista de REFERÊNCIA, que ela aprovou  →  mockup/
    a07_lancadores.py   →  o que o produto MEDE, a cada tique      →  a tela

É o mesmo arranjo que a aba Conexões já provou (`gui/aba_conexoes.html_do_mapa`
serve o gerador e o pacote, e a página regerada saiu byte a byte igual à que ela
aprovou). Sem ele, o desenho e o produto seriam dois donos do mesmo cartão — e o
segundo dono envelhece calado.

**Este módulo não importa NADA do produto.** É desenho puro: entra dado, sai
marcação. Ele é importado pelo gerador (que roda como script solto) e pelo
pacote (que roda dentro da janela), e uma dependência aqui atravessaria para os
dois.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

#: O selo é o resumo de UMA palavra do corpo do cartão.
#:
#: `nao_sei` NASCEU DA MEDIÇÃO, e não do desenho: o produto tem `zero` função
#: que examine Heroic, Lutris, RetroArch, Dolphin ou mGBA — as cinco só aparecem
#: em COMENTÁRIO (`daemon/subsystems/hotkey.py:56`, `daemon/lifecycle.py:2271`,
#: `profiles/schema.py:1336`). Sem este selo, o cartão do Heroic teria de
#: escolher entre `CHEGAM` e `NÃO CHEGAM`, e as duas seriam afirmação sobre um
#: lançador que o produto nunca olhou. **"Não sei" é resposta; palpite não é.**
SELOS = {
    "ok": "CHEGAM",
    "warn": "NÃO CHEGAM",
    "off": "NÃO ACHEI",
    "nao_sei": "NÃO SEI",
}

#: A classe da MOLDURA do cartão, por selo. `nao_sei` divide a moldura apagada
#: com `off` de propósito: as duas dizem "não há o que agir aqui", e um terceiro
#: tom só acrescentaria uma cor para ela decodificar.
MOLDURA = {"ok": "chega", "warn": "impede", "off": "ausente", "nao_sei": "ausente"}

#: A GRADE QUE SEGURA OS SEIS CARTÕES — e ela é constante porque o PACOTE
#: precisa dela, não só o gerador.
#:
#: MEDIDO EM 02/09/2026, e fotografado: a `MOLDURA` só aparecia em
#: :func:`um_cartao`, que é o GERADOR. O pacote emitia cinco endereços por
#: cartão (`-selo`, `-jogos`, `-diz`, `-acoes`, `-fora`) e **nenhum deles é a
#: classe do contêiner** — a página publicada nasceu com os seis cartões em
#: `class="lanc ausente"` (o estado `cartoes(None)`) e a classe ficava lá para
#: sempre. O cartão da Steam mostrava o selo verde `CHEGAM` dentro de uma
#: moldura cinza de *ausente*: **a mesma tela dizendo duas coisas opostas.**
#:
#: A pintura do piloto escreve texto, `innerHTML`, largura, fundo e `value` —
#: não escreve CLASSE. O que ela sabe trocar inteiro é um BLOCO endereçado por
#: seletor CSS (`p.blocos`), e é por isso que o pacote repinta a grade: a classe
#: do contêiner só volta a ser dado junto com o contêiner.
#:
#: O DIA EM QUE O PILOTO GANHAR UM ALVO `classe`, isto vira uma linha por
#: cartão e a grade para de se trocar inteira — está declarado no relato desta
#: frente, em `espera_o_pintor`.
CLASSE_DA_GRADE = "lancadores"
SELETOR_DA_GRADE = f".{CLASSE_DA_GRADE}"


@dataclass(frozen=True)
class Acao:
    """Um botão do cartão. `gesto` vazio = botão sem endereço (só desenho)."""

    rotulo: str
    classe: str = ""
    gesto: str = ""
    #: O `data-v` do botão — qual lançador, ou qual appid. Vai cru para o
    #: `o["v"]` do gesto, e é o que separa "Consertar a Steam" de "Consertar o
    #: Heroic" sem o gesto ter de adivinhar pelo texto do botão.
    v: str = ""


@dataclass(frozen=True)
class Lancador:
    """UM cartão. É o contrato entre o gerador e o pacote."""

    chave: str
    nome: str
    selo: str
    jogos: str
    diz: str
    acoes: tuple[Acao, ...] = ()
    carimbo: str = ""
    #: A lista de jogos DENTRO do cartão (hoje só a Steam a tem). HTML pronto.
    fora: str = ""
    #: O cartão tem lugar para a lista? Se `False`, o gerador nem emite o
    #: contêiner — e um endereço que não existe na página é pintura perdida.
    tem_lista: bool = False
    #: O produto ACHOU este lançador nesta máquina? É o que a contagem do topo
    #: soma, e é um campo próprio de propósito: derivar "encontrado" do SELO
    #: confunde duas perguntas diferentes — *"o lançador está aqui?"* e *"os
    #: controles chegam nele?"*. Um lançador achado cujo interior o produto não
    #: sabe ler é `presente=True` com selo `nao_sei`, e as duas coisas são
    #: verdade ao mesmo tempo.
    presente: bool = False


#: O ESPAÇO DURO É O QUARTO CARACTERE DA TABELA, e ninguém pensa nele. O DOM
#: devolve `&nbsp;` para um U+00A0 que entrou cru — logo emiti-lo cru é a mesma
#: reescrita eterna que o apóstrofo causa, num caractere que um `appmanifest`
#: bem pode trazer.
_DURO = "\u00a0"


def _e(txt: object) -> str:
    """Escapa para HTML **em posição de TEXTO**. O nome do jogo vem do DISCO dela.

    Um `appmanifest` com `&` ou `<` no nome quebraria a marcação do cartão, e um
    nome de jogo é conteúdo de terceiro — a mesma razão pela qual
    `gui/aba_conexoes` escapa o rótulo do aparelho antes de o pôr na tela.

    O `quote=False` NÃO É RELAXAMENTO — é o que impede um LAÇO INFINITO na
    máquina dela, e a razão é o piloto: ele só reescreve quando
    `innerHTML !== valor` (`hefesto_vivo.py:160` no campo, `:303` no bloco). As
    duas comparações são de TEXTO LITERAL, e o lado esquerdo é o que o DOM
    **devolve**, não o que se escreveu. Se a grafia emitida não for a que o DOM
    devolve, a comparação nunca casa e a reescrita não para nunca.

    MEDIDO NO WEBKIT DA JANELA DELA em 02/09/2026 (`<div>` solto, `innerHTML`
    de ida e de volta, os seis caracteres nas duas grafias — 28 casos):

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

    `html.escape(quote=True)` emite `&#x27;` para o apóstrofo e `&quot;` para a
    aspa — e o DOM devolve os dois CRUS no texto. Bastava **um** jogo com
    apóstrofo no nome (a biblioteca dela tem 63) para a lista do cartão e a
    grade inteira serem reescritas **duas vezes por segundo, para sempre**,
    matando o foco e o `:hover` de quem estivesse com o mouse num botão.

    A régua que segura isto é `test_a_marcacao_volta_igual_do_dom`, e ela não
    digita a tabela acima: reserializa a marcação emitida pelas regras medidas e
    exige que o texto volte idêntico.
    """
    return html.escape(str(txt if txt is not None else ""),
                       quote=False).replace(_DURO, "&nbsp;")


def _a(txt: object) -> str:
    """Escapa para HTML **em posição de ATRIBUTO** — o `_e` mais a aspa.

    A DIFERENÇA É UMA LINHA e ela é obrigatória nos dois sentidos: dentro de um
    atributo entre aspas duplas, uma aspa crua FECHA o atributo (foi medido:
    `data-v="a"b"` volta do DOM como dois atributos), e um `&#x27;` volta cru.
    Um único escape para os dois lugares erra sempre num dos dois.

    TODO ATRIBUTO DESTE MÓDULO USA ASPAS DUPLAS — é o que torna a tabela acima o
    contrato inteiro. O `<` e o `>` continuam escapados porque o WebKit os
    devolve escapados **também no atributo**, e não porque a marcação precise.
    """
    return _e(txt).replace('"', "&quot;")


def selo_html(selo: str) -> str:
    """O selo com a CLASSE certa — e é por isso que ele é pintado como `html`.

    A pintura do piloto escreve `textContent` por padrão, e o `textContent` não
    troca a cor: um cartão que passasse de `CHEGAM` (verde) para `NÃO SEI`
    ficaria com a palavra nova e o verde velho. O `data-hef-alvo="html"` do
    esqueleto existe para exatamente isto, e o alvo é o INVÓLUCRO — o `<span>`
    com a classe entra no innerHTML, e não ao redor dele.
    """
    if selo not in SELOS:
        raise KeyError(
            f"selo {selo!r} não existe. Os que existem estão em `SELOS`, e "
            f"inventar um aqui deixaria o cartão sem cor — a única coisa que "
            f"esta aba mostra sem ler.")
    return f'<span class="lanc-selo {selo}">{SELOS[selo]}</span>'


def carimbo_html(texto: str) -> str:
    """O carimbo verde, ou VAZIO. Vazio some do cartão, e é o certo.

    Um carimbo que dissesse "0 jogos já sabem por onde entrar" ocuparia a linha
    para não dizer nada — e o desenho o pôs na fileira dos botões justamente
    para não custar altura quando não há notícia.
    """
    return f'<span class="carimbo">◆ {_e(texto)}</span>' if texto else ""


def acao_html(a: Acao) -> str:
    """Um botão. Sem `gesto`, ele nasce SEM endereço — e é decisão, não esquecimento.

    A regra da casa: *"o que NÃO tem dono não vira botão que finge"*. Um
    `data-gesto` num botão que ninguém atende faz o piloto recusar dizendo o
    nome, o que é honesto; mas um `data-gesto` num botão que o produto não sabe
    fazer seria pior — a recusa aparece só no terminal, e na tela o clique some.
    """
    classe = f"btn {a.classe}".strip()
    endereco = f' data-gesto="{_a(a.gesto)}"' if a.gesto else ""
    valor = f' data-v="{_a(a.v)}"' if a.v else ""
    return f'<button class="{classe}"{endereco}{valor}>{_e(a.rotulo)}</button>'


#: O QUE VAI NO LUGAR DE UMA FILEIRA DE BOTÕES VAZIA — e ele não é enfeite.
#:
#: O `escrever()` do BOOTSTRAP troca o vazio pelo TRAVESSÃO, e para um campo de
#: VALOR isso é o certo: "não há valor" se lê `—`. Para um contêiner de HTML é
#: errado, e foi fotografado em 02/09/2026: os quatro cartões `NÃO ACHEI`
#: nasceram com um traço solto pendurado onde os botões tinham estado, dizendo
#: nada. O mesmo traço já estava, desde antes, no pé do cartão da Steam com a
#: lista vazia.
#:
#: **O conserto de raiz é no `escrever()`**, que precisa separar alvo `html`
#: (vazio = NADA) de alvo de texto (vazio = travessão) — está no relato desta
#: frente, e mora em `hefesto_vivo.py`, que não é território desta aba.
#:
#: Um COMENTÁRIO HTML é o que o desenho pode fazer sozinho: o valor não é
#: vazio (logo o travessão não entra), o navegador o renderiza como nada, e a
#: fileira fica com a altura do seu próprio `padding-top` — que é o que ela
#: teria se o produto pudesse escrever vazio de verdade.
FILEIRA_VAZIA = "<!-- nada a oferecer neste cartão -->"

#: O QUE VAI NUM CONTÊINER DE LISTA QUE AINDA NÃO TEM O QUE LISTAR — e ele NÃO
#: É UMA FRASE, de propósito.
#:
#: FOTOGRAFADO EM 02/09/2026, e a cura anterior alcançou só um dos três estados:
#: `lista_de_jogos` ganhou :data:`LISTA_VAZIA`, mas os DOIS ramos de saída
#: antecipada de :func:`cartao_da_steam` — a primeira meia volta (`lida is
#: None`) e a Steam ilegível (`lida.erros`) — devolviam o cartão com `fora` no
#: padrão `""`. Como `tem_lista=True`, `valores_do_cartao` emitia
#: `steam-fora=""`, e o `escrever()` do BOOTSTRAP troca vazio por travessão
#: ANTES de despachar o alvo (`hefesto_vivo.py:118`), inclusive para
#: `alvo === 'html'`. **O da Steam ilegível é permanente** — justo a tela em que
#: ela precisa ler uma mensagem, com um traço mudo pendurado embaixo.
#:
#: POR QUE UM COMENTÁRIO E NÃO UMA FRASE: nos dois estados o produto **não sabe**
#: o que há na lista. Escrever "nenhum jogo com pendência" ali seria afirmar o
#: resultado de uma leitura que não aconteceu — a forma exata do defeito que
#: esta aba nasceu para matar. O comentário não é vazio (logo o travessão não
#: entra), o navegador o renderiza como NADA, e a tela fica igual ao desenho que
#: ela aprovou, onde o contêiner nasce vazio.
SEM_LISTA = "<!-- ainda não há lista para este cartão -->"

#: A frase da lista de jogos VAZIA do cartão da Steam. Ela existe pela mesma
#: razão do de cima, e diz o que o travessão não dizia: a lista tem QUATRO
#: origens (falta o atalho · linha intocável · você tirou · você dispensou), e
#: vazia significa que nenhuma delas tem item — não que ninguém olhou.
LISTA_VAZIA = ("Nenhum jogo com pendência, e nenhum que você tenha tirado ou "
               "dispensado.")


def acoes_html(lanc: Lancador) -> str:
    """A fileira de botões DO CARTÃO, com o carimbo no fim dela.

    ELA É PINTADA INTEIRA, e a razão é medida: no cartão da Steam os botões
    MUDAM com o estado — `Consertar` só existe quando há o que consertar. Se a
    fileira fosse estática, ou o `Consertar` ficaria aceso sobre uma biblioteca
    inteira em ordem (um clique que não conserta nada), ou não existiria no dia
    em que a Steam comesse a linha — e o botão que a aba existe para oferecer
    nunca apareceria.

    O CARIMBO VAI AQUI DENTRO porque o desenho o pôs aqui: como linha própria
    ele custava 21px que SÓ o cartão da Steam pagava, e a fileira dele nascia
    21px abaixo da do cartão vizinho.

    A QUEBRA DE LINHA E O RECUO SÃO PARTE DO VALOR, e isso é cura — medida na
    tela em 02/09/2026, com o piloto rodando 40 segundos. O gerador escrevia
    ``<div class="acoes">\\n{acoes_html}\\n        </div>`` e o pacote pintava
    ``acoes_html`` **sem** a moldura de espaço; as duas grafias do MESMO valor
    ficavam eternamente diferentes, e com a grade sendo repintada como bloco
    isso virou um PING-PONG: o bloco reescrevia a fileira com o espaço, o campo
    a reescrevia sem, e o piloto contava pintura em **81 de 81 voltas** — 2 por
    segundo, para sempre, destruindo o foco e o `:hover` de quem estivesse com o
    mouse em cima de um botão.

    Com o espaço DENTRO do valor, a página sai byte a byte igual à de antes e as
    duas grafias passam a ser uma só. Quem segura isto é
    `test_o_valor_pintado_e_o_valor_da_grade_sao_a_mesma_coisa`.
    """
    botoes = "\n".join(f"          {acao_html(a)}" for a in lanc.acoes)
    carimbo = carimbo_html(lanc.carimbo)
    if not botoes and not carimbo:
        miolo = FILEIRA_VAZIA
    else:
        miolo = f"{botoes}\n          {carimbo}" if carimbo else botoes
    return f"\n{miolo}\n        "


def um_cartao(lanc: Lancador) -> str:
    """O cartão inteiro, com os endereços que o pacote pinta.

    QUATRO ENDEREÇOS POR CARTÃO, e o quinto só onde há lista. Todos com o prefixo
    da `chave` porque a página tem seis cartões e um `data-campo="selo"` sozinho
    seria pintado nos seis com o mesmo valor — o defeito que a distribuição de
    lista do piloto faz de propósito, e que aqui seria acidente.
    """
    # A `chave` SÓ APARECE EM ATRIBUTO nesta função (`data-lancador`,
    # `data-campo`), então ela é escapada como atributo — ver :func:`_a`.
    k = _a(lanc.chave)
    # A FILEIRA SAI NUMA VARIÁVEL para a linha caber nos 100 caracteres do
    # `ruff` — o HTML emitido é o mesmo caractere por caractere, e a moldura de
    # espaço continua vindo de dentro de `acoes_html`, que é onde ela tem de
    # estar para o valor pintado e o da grade serem UM só.
    acoes = (f'<div class="acoes" data-campo="{k}-acoes" '
             f'data-hef-alvo="html">{acoes_html(lanc)}</div>')
    lista = (
        f'\n        <div class="lanc-fora" data-campo="{k}-fora" '
        f'data-hef-alvo="html">{lanc.fora}</div>'
        if lanc.tem_lista else ""
    )
    return f'''      <div class="lanc {MOLDURA[lanc.selo]}" data-lancador="{k}">
        <div class="lanc-topo">
          <span class="lanc-nome">{_e(lanc.nome)}</span>
          <span data-campo="{k}-selo" data-hef-alvo="html">{selo_html(lanc.selo)}</span>
          <span class="lanc-jogos" data-campo="{k}-jogos">{_e(lanc.jogos)}</span>
        </div>
        <div class="lanc-diz" data-campo="{k}-diz" data-hef-alvo="html">{lanc.diz}</div>
        {acoes}{lista}
      </div>'''


def cartoes_html(lancadores: list[Lancador]) -> str:
    """A grade inteira. Usada pelo gerador; o pacote pinta campo a campo."""
    return "\n".join(um_cartao(x) for x in lancadores)


def valores_do_cartao(lanc: Lancador) -> dict[str, str]:
    """O que o PACOTE emite para aquele cartão — os mesmos endereços de cima.

    ESCRITO AQUI, e não no pacote, para que os dois lados não possam divergir:
    quem acrescentar um endereço em `um_cartao` e esquecer daqui deixa um campo
    com o valor do desenho para sempre, e é isso que a régua da aba cobra.
    """
    fora = {
        f"{lanc.chave}-selo": selo_html(lanc.selo),
        f"{lanc.chave}-jogos": lanc.jogos,
        f"{lanc.chave}-diz": lanc.diz,
        f"{lanc.chave}-acoes": acoes_html(lanc),
    }
    if lanc.tem_lista:
        fora[f"{lanc.chave}-fora"] = lanc.fora
    return fora


@dataclass(frozen=True)
class JogoNaLista:
    """Uma linha da lista de jogos dentro do cartão."""

    appid: str
    rotulo: str
    #: O que a linha diz do jogo — "nunca recebeu", "perdeu", "você tirou".
    porque: str
    #: O botão da linha: `("tirar-daqui", "Não usar neste jogo")` ou o inverso.
    gesto: str = ""
    botao: str = ""


def linhas_de_jogos(itens: list[JogoNaLista], vazio: str = "") -> str:
    """A lista de jogos do cartão, ou a frase de lista vazia.

    O `data-v` DE CADA LINHA É O APPID, e não o rótulo: dois jogos podem ter o
    mesmo nome na biblioteca (uma demo e o jogo), e `rotulo_do_jogo` cai para
    `appid NNNN` quando o manifesto sumiu. Clicar por nome tiraria o wrapper do
    jogo errado — é a mesma razão pela qual a aba Conexões endereça o aparelho
    pelo `nome_do_kernel` e não pelo rótulo.
    """
    if not itens:
        return f'<div class="lanc-vazio">{_e(vazio)}</div>' if vazio else ""
    linhas = []
    for j in itens:
        botao = (
            f'<button class="btn mini" data-gesto="{_a(j.gesto)}" '
            f'data-v="{_a(j.appid)}">{_e(j.botao)}</button>'
            if j.gesto else ""
        )
        linhas.append(
            f'<div class="lanc-jogo"><span class="lanc-jogo-nome">{_e(j.rotulo)}</span>'
            f'<span class="lanc-jogo-porque">{_e(j.porque)}</span>{botao}</div>'
        )
    return "".join(linhas)


def conta_html(achados: int, impedidos: int) -> str:
    """A contagem do quadro: `N encontrados · M com impedimento`.

    ELA JÁ ERA DERIVADA no gerador (a aba dizia "6 encontrados" contando o
    cartão que ela mesma carimba `NÃO ACHEI`), e continua sendo — o que muda é
    de ONDE: da lista de cartões que o produto montou, e não da que ele digitou.
    """
    return (f'{_plural(achados, "encontrado", "encontrados")} '
            f'<span class="sep">·</span> '
            f'{_plural(impedidos, "com impedimento", "com impedimentos")}')


#: OS ENDEREÇOS QUE UM CARTÃO PRODUZ, para a régua da aba os cobrar sem
#: reescrever a lista. Régua que digita o que devia LER é o defeito que esta
#: casa nomeou onze vezes em 26/08.
SUFIXOS = ("-selo", "-jogos", "-diz", "-acoes")
SUFIXO_DA_LISTA = "-fora"


# ---------------------------------------------------------------------------
# O QUE O DISCO RESPONDE, e os seis cartões que saem dele
#
# ISTO MORA NO DESENHO, e não no pacote, por uma razão de ferramenta: o gerador
# `aba07.py` roda como SCRIPT SOLTO (`python3 aba07.py`) e não pode importar
# `pacotes/`, que puxa os dez pacotes e o produto inteiro. Com os cartões aqui,
# o gerador emite a página de REFERÊNCIA chamando `cartoes(None)` — o mesmo
# estado que a tela mostra na primeira meia volta, antes de a leitura voltar —
# e o pacote emite os mesmos cartões com o dado real. **Um dono, dois dados.**
#
# É o que impede o número digitado de voltar: não há onde digitá-lo.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemCenso:
    """Um lançador cujo INTERIOR o produto não sabe ler — e onde procurá-lo.

    OS DOIS SABERES SÃO SEPARADOS, e confundi-los foi o defeito que este
    arquivo nasceu para curar. *"Sei ler a biblioteca dele"* e *"ele está
    instalado aqui"* são perguntas diferentes, e o produto responde a SEGUNDA
    hoje, de graça: um lançador instalado publica um `.desktop` nas pastas que
    a spec XDG declara, ou põe o executável no `PATH`.

    Enquanto só a primeira existia, os cinco cartões diziam `NÃO SEI` por
    CONSTANTE — o pacote escrevia sempre a mesma palavra, e a tela não tinha
    como diferir *"o produto mediu e não sabe"* de *"ninguém pintou"*. É a
    forma exata do defeito desta casa: **o desenho fingindo ser produto.**

    :param atalhos: os `stem` de `.desktop` que denunciam o lançador. Sem
        glob e sem casamento por prefixo: `dolphin-emu` é o emulador e
        `dolphin` é o gerenciador de arquivos do KDE — casar por prefixo
        acusaria o Dolphin em toda máquina com KDE instalado.
    :param comandos: o que procurar no `PATH` quando não há `.desktop`. É o
        caso do Flatpak, que é PACOTE e não aplicativo: ele não publica
        atalho próprio, só o comando.
    """

    chave: str
    nome: str
    atalhos: tuple[str, ...] = ()
    comandos: tuple[str, ...] = ()


#: OS LANÇADORES CUJO INTERIOR O PRODUTO NÃO LÊ. A lista é dado, e não `if`: no
#: dia em que alguém escrever o censo do Heroic, ele SAI daqui e ganha cartão
#: próprio.
#:
#: A PROVA DE QUE NENHUM É LIDO POR DENTRO, medida em 02/09/2026:
#:     grep -rniE "heroic|lutris|retroarch|dolphin|mgba" src --include="*.py"
#: devolve CINCO linhas fora desta aba, e as cinco são COMENTÁRIO
#: (`daemon/subsystems/hotkey.py:56`, `daemon/lifecycle.py:2271`,
#:  `daemon/subsystems/game_signal.py:97`, `daemon/lifecycle.py:4169`,
#:  `profiles/schema.py:1336`). Zero função, zero chamada — e o
#: `test_os_cinco_lancadores_sem_fonte_continuam_sem_fonte` é quem segura isso.
#:
#: OS IDENTIFICADORES SÃO OS DE VERDADE, e as duas formas de cada um entram: o
#: `app-id` do Flatpak (que é como a máquina dela os teria, pelos 54 atalhos em
#: `~/.local/share/flatpak/exports/share/applications`) e o nome nativo do
#: pacote da distribuição.
SEM_FONTE: tuple[SemCenso, ...] = (
    SemCenso("heroic", "Heroic (Epic · GOG)",
             ("com.heroicgameslauncher.hgl", "heroic"), ("heroic",)),
    SemCenso("lutris", "Lutris", ("net.lutris.Lutris", "lutris"), ("lutris",)),
    SemCenso("flatpak", "Flatpak", (), ("flatpak",)),
    SemCenso("retroarch", "RetroArch",
             ("org.libretro.RetroArch", "retroarch"), ("retroarch",)),
    SemCenso("emuladores", "Dolphin · mGBA",
             ("org.DolphinEmu.dolphin-emu", "dolphin-emu", "io.mgba.mGBA",
              "mgba-qt", "mgba"),
             ("dolphin-emu", "mgba-qt", "mgba")),
)

#: A STEAM TAMBÉM SE PROCURA — 02/09/2026, e ela nasceu de uma acusação provada.
#:
#: O cartão da Steam era o único com CENSO, e por isso o único cuja PRESENÇA
#: ninguém mediu: `presente=True` era constante. Medido com o `HOME` desviado
#: para uma casa de mentira, sem Steam nenhuma e com o `PATH` vazio:
#:
#:     conta_do_topo = '1 encontrado · 0 com impedimentos'
#:     steam: selo 'ok' (CHEGAM), presente True,
#:            'Os controles chegam. O atalho de inicialização está no lugar em
#:             0 jogos da sua biblioteca.'
#:
#: Uma máquina SEM Steam recebia o selo VERDE e a promessa de que os controles
#: chegam — a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na cor verde, que é a frase com
#: que esta aba nasceu. Os outros cinco cartões diziam `NÃO ACHEI` na mesma tela.
#:
#: A CURA É A MEDIÇÃO QUE JÁ EXISTIA, aplicada ao sexto: as mesmas pastas de
#: `.desktop` e o mesmo `PATH` que respondem pelos cinco respondem por esta.
#: Ela NÃO entra em :data:`SEM_FONTE` — o interior da Steam o produto LÊ, e é
#: essa a pergunta daquela lista. São duas perguntas, e continuam separadas.
#:
#: OS IDENTIFICADORES: `steam.desktop` é o do pacote da distribuição (medido
#: nesta bancada, em `/usr/share/applications`), `com.valvesoftware.Steam` é o
#: da Flathub e `steam-native` é o da instalação sem o runtime. O comando entra
#: pelo mesmo motivo dos outros — nesta bancada ele é `/usr/games/steam`, que
#: nem sequer está no `/usr/bin`.
A_STEAM = SemCenso("steam", "Steam",
                   ("steam", "com.valvesoftware.Steam", "steam-native"),
                   ("steam", "steam-native"))

#: OS SEIS QUE O PRODUTO PROCURA em disco. É esta lista que o pacote percorre —
#: :data:`SEM_FONTE` responde outra coisa (*"sei ler a biblioteca dele?"*) e
#: percorrê-la para procurar deixava a Steam de fora da única pergunta que o
#: produto sabe responder sobre os seis sem inventar.
PROCURADOS: tuple[SemCenso, ...] = (A_STEAM, *SEM_FONTE)

#: A frase de quem AINDA NÃO PROCUROU — a primeira meia volta, antes de a
#: leitura de disco voltar. Ela diz as TRÊS coisas que quem lê precisa: que o
#: produto não olhou, que o perfil casa por processo e janela (logo um jogo
#: aberto de lá pode funcionar), e o que falta para o cartão virar medição.
DIZ_SEM_FONTE = (
    "<b>Ainda não sei olhar este lançador.</b> O Hefesto casa o perfil pelo "
    "nome do processo e pela janela, então um jogo aberto por aqui pode "
    "funcionar — o que falta é o produto <i>medir</i>, e nenhuma linha dele "
    "olha para cá hoje."
)

#: A frase de quem PROCUROU E ACHOU. O `{onde}` é o atalho ou o comando que
#: denunciou o lançador — dizer ONDE é o que separa esta frase de um palpite,
#: e é o que deixa ela conferir a resposta sem acreditar em mim.
DIZ_ACHEI = (
    "<b>Achei este lançador aqui</b> (<code>{onde}</code>), mas ainda não sei "
    "olhar <i>dentro</i> dele: o produto não lê a biblioteca deste lançador. "
    "O Hefesto casa o perfil pelo nome do processo e pela janela, então um "
    "jogo aberto por aqui pode funcionar."
)

#: A frase de quem PROCUROU E NÃO ACHOU. Ela nomeia as duas buscas, porque uma
#: instalação fora das duas (um AppImage solto, um script no `~/bin`) existe e
#: esta frase não pode afirmar que o lançador não está na máquina — só que o
#: produto não o achou por onde sabe procurar.
DIZ_NAO_ACHEI = (
    "<b>Não achei este lançador nesta máquina.</b> Procurei o atalho "
    "<code>.desktop</code> nas pastas de aplicativos e o comando no "
    "<code>PATH</code>. Instalado de outro jeito (um AppImage solto, por "
    "exemplo) ele não aparece aqui — e o perfil continua casando pelo nome do "
    "processo e pela janela."
)

#: O que o cartão da Steam mostra enquanto a primeira leitura não voltou.
#: **Nunca um número** — um número que ainda não foi lido é um número inventado.
AINDA_LENDO = "…"

#: A chave do único cartão com fonte.
STEAM = "steam"


@dataclass(frozen=True)
class Leitura:
    """O que o disco respondeu sobre a Steam. É o contrato pacote → desenho.

    Ele é FRIO de propósito — só tuplas de texto, nenhum objeto do motor. Assim
    o desenho não importa `sentinela_do_wrapper` (e o gerador continua rodando
    sem o produto), e a régua da aba monta uma `Leitura` à mão para provar cada
    estado do cartão sem tocar no disco.
    """

    #: appids cuja linha de inicialização JÁ chama o wrapper.
    com_wrapper: tuple[str, ...] = ()
    #: os que não chamam e o produto CONSEGUE repor: `(appid, rótulo, porquê)`.
    reparaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que não chamam e ninguém deve tocar (lista de IGNORE estendida à mão).
    intocaveis: tuple[tuple[str, str, str], ...] = ()
    #: os que ELA tirou, no `jogos_sem_wrapper.txt`: `(appid, rótulo)`.
    recusados: tuple[tuple[str, str], ...] = ()
    #: os que ELA dispensou do LEMBRETE, no `launch_dialog_dismissed.json`:
    #: `(appid, rótulo)`. É outra lista e outra pergunta — ver `lista_de_jogos`.
    dispensados: tuple[tuple[str, str], ...] = ()
    #: quantos jogos estão INSTALADOS — o vdf guarda linha de jogo desinstalado.
    instalados: int = 0
    #: quantos jogos já têm PONTE CONFIRMADA no perfil, de
    #: `prontuario_dos_jogos.pontes_confirmadas`. É a fonte do carimbo que o
    #: desenho prometia (`◆ 3 jogos já sabem por onde entrar`) e que nasceu
    #: digitado — medido em 02/09/2026, o produto respondia ZERO.
    pontes: int = 0
    #: Onde cada lançador PROCURADO foi achado: `(chave, local)`. Local vazio =
    #: **procurei e não achei**; chave AUSENTE do mapa = **não procurei**. A
    #: distinção é o ponto inteiro: as duas viram frases diferentes na tela.
    #: A `steam` entrou no mapa em 02/09 — ver :data:`A_STEAM`.
    onde_estao: tuple[tuple[str, str], ...] = ()
    #: a frase da sentinela, que já nomeia o jogo e já diz o que vai acontecer.
    frase: str = ""
    erros: tuple[str, ...] = ()

    @property
    def onde_esta_a_steam(self) -> str | None:
        """Onde a Steam foi achada; `''` = procurei e não achei; `None` = não procurei.

        A TERCEIRA RESPOSTA É A QUE IMPORTA. Uma `Leitura` montada à mão (a
        régua desta aba monta várias) não tem a `steam` no mapa, e ali `None`
        quer dizer *"esta leitura não fala de presença"* — o cartão então segue
        só o censo, que era todo o comportamento anterior. Colapsar `None` em
        `''` faria toda régua antiga passar a ver `NÃO ACHEI`.
        """
        return dict(self.onde_estao).get(STEAM)

    @property
    def viu_a_biblioteca(self) -> bool:
        """A leitura ALCANÇOU a biblioteca da Steam de algum jeito?

        POR QUE ELA EXISTE, e não basta olhar `onde_esta_a_steam`: as duas
        buscas respondem coisas diferentes e podem discordar sem que nenhuma
        esteja errada. Uma Steam instalada por um caminho que os três `.desktop`
        conhecidos não cobrem (um AppImage, um script no `~/bin`) não aparece na
        procura — e ainda assim o `localconfig.vdf` dela está lá, com a
        biblioteca inteira. Dizer `NÃO ACHEI` sobre uma biblioteca que o produto
        acabou de ler seria trocar um erro por outro.

        O `erros` ENTRA na conta: um vdf ilegível é um vdf que EXISTE.
        """
        return bool(self.erros or self.com_wrapper or self.reparaveis
                    or self.intocaveis or self.recusados or self.instalados)


def _plural(n: int, um: str, muitos: str) -> str:
    return f"{n} {um if n == 1 else muitos}"


def lista_de_jogos(lida: Leitura) -> str:
    """As linhas dentro do cartão da Steam: quem falta, quem ELA tirou, e quem
    ELA mandou não perguntar mais.

    OS INTOCÁVEIS APARECEM SEM BOTÃO, de propósito: o produto não os repõe (o
    `apply_wrapper_vdf_text` os pula por construção) e "tirar daqui" um jogo que
    já está fora do reparo não mudaria nada — um botão que não muda nada é o que
    esta casa chama de botão que finge.

    OS DISPENSADOS TÊM BOTÃO, e ele nasceu em 02/09/2026 por decisão dela. Eles
    são o `launch_dialog_dismissed.json`, escrito pelo botão *"Não perguntar
    para este jogo"* do lembrete da GTK — e até hoje de manhã **nenhuma tela
    desta casa os mostrava**. Mostrar curou o silêncio pela metade: a dispensa
    continuava sendo um gesto SEM VOLTA pela tela, porque o motor só tinha
    `add_dismissed_appid`. Agora tem o par (`remove_dismissed_appid`), e a linha
    ganha *"Voltar a perguntar"* — pelo mesmo motivo que o "Voltar a usar"
    existe ao lado do "Não usar neste jogo": *um gesto que só vai numa direção
    deixa a pessoa presa no estado em que clicou.*

    OS INTOCÁVEIS CONTINUAM SEM BOTÃO, e a diferença é a que separa as duas
    listas: ali não há gesto que mude nada; aqui há.

    A LISTA É OUTRA, e não a mesma dos recusados: `jogos_sem_wrapper.txt` diz
    *"não ponha o atalho neste jogo"* e o dispensado diz *"não me lembre deste
    jogo"*. Um jogo pode estar num, no outro, ou nos dois — juntá-las numa só
    apagaria a diferença que faz a pessoa entender o que ela mesma pediu.
    """
    itens = [
        JogoNaLista(appid=a, rotulo=r, porque=p,
                    gesto="tirar-daqui", botao="Não usar neste jogo")
        for a, r, p in lida.reparaveis
    ]
    itens += [JogoNaLista(appid=a, rotulo=r, porque=p)
              for a, r, p in lida.intocaveis]
    itens += [
        JogoNaLista(appid=a, rotulo=r, porque="você tirou este jogo",
                    gesto="voltar-a-usar", botao="Voltar a usar")
        for a, r in lida.recusados
    ]
    itens += [
        JogoNaLista(appid=a, rotulo=r,
                    porque="você mandou não perguntar mais por este jogo",
                    gesto="voltar-a-perguntar", botao="Voltar a perguntar")
        for a, r in lida.dispensados
    ]
    return linhas_de_jogos(itens, vazio=LISTA_VAZIA)


def cartao_da_steam(lida: Leitura | None) -> Lancador:
    """O ÚNICO cartão com fonte, e cada palavra dele sai de uma medição.

    O SELO SEGUE `reparaveis`, e não a soma dos faltantes: um jogo com a lista
    de IGNORE estendida à mão está sem o wrapper e **não deve ser tocado** —
    remover só o trecho do Hefesto deixaria um fragmento-comando que impede o
    jogo de abrir. Contá-lo como "não chega" acenderia um `Consertar` que não
    conserta aquele jogo.

    A PRESENÇA DEIXOU DE SER CONSTANTE — 02/09/2026, e a acusação foi provada
    antes de curada. Com o `HOME` desviado para uma casa de mentira e o `PATH`
    vazio (nenhuma Steam, nenhum vdf, nenhum jogo), este cartão respondia:

        selo 'ok' (**CHEGAM**) · presente True · "1 encontrado" no topo
        "Os controles chegam. O atalho de inicialização está no lugar em 0
         jogos da sua biblioteca."

    Uma máquina sem Steam recebia o selo VERDE e a promessa — enquanto os cinco
    cartões vizinhos, na mesma tela, diziam `NÃO ACHEI`. Era o único cartão cuja
    presença ninguém mediu, porque era o único com censo: ter fonte para o
    INTERIOR não responde se o lançador está aqui.

    AS DUAS PERGUNTAS CONTINUAM SEPARADAS, e é por isso que o `NÃO ACHEI` exige
    as DUAS respostas negativas (:meth:`Leitura.viu_a_biblioteca`): uma Steam
    instalada por um caminho que os três `.desktop` conhecidos não cobrem não
    aparece na procura, e ainda assim a biblioteca dela foi lida. Dizer "não
    achei" sobre uma biblioteca recém-lida seria trocar um erro por outro.
    """
    # A FILEIRA É A QUE ELA APROVOU, botão por botão: o cartão `CHEGAM` do
    # desenho tem `Abrir o lançador` + `Criar perfil para um jogo`, e o
    # `NÃO CHEGAM` tem `Consertar` + `Ver o que impede` + `Abrir o lançador`.
    # NÃO acrescentei um `Procurar de novo` aqui: ele já está no topo do quadro,
    # e um segundo botão com o mesmo texto na mesma tela é a quebra de "mesma
    # família, mesma coisa" que esta aba já pagou uma vez (o `.lanc .btn` que
    # encolhia). A exceção é o cartão em ERRO, o único estado em que ele
    # responde uma pergunta que o cartão fez.
    abrir = Acao("Abrir o lançador", "", "", "")
    criar = Acao("Criar perfil para um jogo", "", "", "")
    # O `fora=SEM_LISTA` DOS DOIS RAMOS É CURA, e não enfeite: sem ele o
    # `steam-fora` sai vazio, o `escrever()` do bootstrap o troca por `—` e a
    # tela ganha um traço solto no pé do cartão. Ver :data:`SEM_LISTA`.
    if lida is None:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos=AINDA_LENDO,
            diz="Estou lendo a sua biblioteca da Steam…",
            acoes=(abrir, criar), fora=SEM_LISTA, tem_lista=True)
    if lida.onde_esta_a_steam == "" and not lida.viu_a_biblioteca:
        # PROCUREI E NÃO ACHEI, e a frase é a MESMA dos outros cinco
        # (:data:`DIZ_NAO_ACHEI`) de propósito: ela já nomeia as duas buscas e
        # já ressalva a instalação fora delas. Uma segunda redação para o mesmo
        # fato seria texto de tela que ela não decidiu, e duas frases que
        # envelhecem separadas — o defeito que a decisão 14 dela nomeou
        # ("uma frase, um dono").
        return Lancador(
            chave=STEAM, nome="Steam", selo="off", jogos="—",
            diz=DIZ_NAO_ACHEI, acoes=(abrir,), fora=SEM_LISTA, tem_lista=True)
    if lida.erros:
        return Lancador(
            chave=STEAM, nome="Steam", selo="nao_sei", jogos="—",
            diz=("<b>Não consegui ler a biblioteca da Steam</b> — "
                 f"{_e(lida.erros[0])}. Nada foi alterado."),
            acoes=(Acao("Procurar de novo", "", "procurar", STEAM), abrir, criar),
            fora=SEM_LISTA, tem_lista=True)

    falta = len(lida.reparaveis)
    if falta:
        # A FRASE É DA SENTINELA, e não minha: ela já nomeia o jogo, já diz o
        # que ele perdeu e já diz o que vai acontecer. "1 jogo com problema" é
        # exatamente o texto que deixou o Pragmata quebrado a noite inteira.
        diz = _e(lida.frase) or (
            f"<b>Sem wrapper</b> — {_plural(falta, 'jogo', 'jogos')} sem o "
            "atalho de inicialização do Hefesto na linha de comando.")
        acoes: tuple[Acao, ...] = (
            Acao("Consertar", "verde", "consertar", STEAM),
            Acao("Ver o que impede", "", "ver-o-que-impede", STEAM), abrir)
        selo = "warn"
    else:
        diz = ("Os controles chegam. O atalho de inicialização está no lugar em "
               f"{_plural(len(lida.com_wrapper), 'jogo', 'jogos')} da sua "
               "biblioteca.")
        acoes = (abrir, criar)
        selo = "ok"

    return Lancador(
        chave=STEAM, nome="Steam", selo=selo,
        jogos=_plural(lida.instalados, "jogo instalado", "jogos instalados"),
        diz=diz, acoes=acoes, carimbo=carimbo_da_steam(lida),
        fora=lista_de_jogos(lida), tem_lista=True,
        # ERA `True` CRAVADO, e o `True` cravado é o que fazia a conta do topo
        # dizer "1 encontrado" numa máquina sem Steam nenhuma. As duas respostas
        # entram porque **ou uma ou outra** basta: achei o lançador em disco, ou
        # li a biblioteca dele. O ramo de cima já devolveu quando as duas são
        # negativas, então aqui pelo menos uma é verdadeira — escrever a conta
        # mesmo assim é o que impede a constante de voltar por descuido.
        presente=bool(lida.onde_esta_a_steam) or lida.viu_a_biblioteca)


def carimbo_da_steam(lida: Leitura) -> str:
    """As duas notícias do carimbo, na ordem em que ela precisa lê-las.

    O CARIMBO NÃO É SÓ BOA NOTÍCIA. Ele é o único lugar que sobra no cartão, e
    calar sobre um jogo que o produto DECIDIU não tocar é como ele fica sem o
    atalho para sempre sem ninguém saber.

    A PONTE CONFIRMADA VOLTA AO CARTÃO, e ela é a promessa que o desenho fazia
    e o produto tinha largado: o HTML de 02/09 dizia ``◆ 3 jogos já sabem por
    onde entrar`` com o número DIGITADO, e `prontuario_dos_jogos` já respondia a
    mesma pergunta desde sempre, sem um chamador. Agora responde daqui — e no
    dia em que ela confirmar a primeira ponte, o carimbo acende sozinho.

    ZERO SOME, e é o mesmo critério que `carimbo_html` já aplicava: *"0 jogos
    já sabem por onde entrar"* ocuparia a linha para não dizer nada.
    """
    partes: list[str] = []
    if lida.pontes:
        partes.append(f"{_plural(lida.pontes, 'jogo já sabe', 'jogos já sabem')} "
                      "por onde entrar")
    if lida.intocaveis:
        partes.append(f"{_plural(len(lida.intocaveis), 'jogo', 'jogos')} com a "
                      "linha intocável — só reparo manual")
    return " · ".join(partes)


def cartao_sem_censo(item: SemCenso, onde: str | None) -> Lancador:
    """Um dos cinco cartões cujo INTERIOR o produto não lê — em três estados.

    E OS TRÊS SÃO DIFERENTES, que é a razão de esta função existir:

    ==============  ============  =========================================
    ``onde``        selo          o que a tela passa a dizer
    ==============  ============  =========================================
    ``None``        ``nao_sei``   ainda não procurei (a primeira meia volta)
    ``""``          ``off``       procurei e NÃO ACHEI nesta máquina
    um caminho      ``nao_sei``   achei AQUI, e ainda não sei olhar dentro
    ==============  ============  =========================================

    O SELO ``off`` ESTAVA MORTO ATÉ HOJE. `SELOS["off"] = "NÃO ACHEI"` existia
    no desenho desde que ele nasceu e NENHUM caminho o produzia — os seis
    cartões saíam `ok`, `warn` ou `nao_sei`. Ele era a palavra que faltava para
    a tela poder dizer o que o produto mediu.

    O BOTÃO FICA NOS TRÊS ESTADOS — decisão dela, 02/09/2026, e ela DESFAZ uma
    mudança que ninguém tinha submetido a ela. O estado `off` nasceu (na tarde
    de 02/09) com `acoes=()`, pelo argumento de que "Abrir o lançador" sobre um
    lançador ausente seria botão que finge. O argumento tem mérito e **não é
    desta frente decidi-lo**: o desenho que ela aprovou tem o botão nos CINCO
    cartões, e a tela dela não pode perder um botão por conta de um raciocínio
    que ela não viu. Se ele deve sumir quando o lançador não está aqui, quem
    diz é ela — está em `espera_a_palavra_dela`, junto com as três frases.

    (Ele continua sem dono — `SEM_DONO["abrir-lancador"]` — nos seis cartões,
    exatamente como no cartão da Steam. Sumir só neste era, além de mudança não
    pedida, a única incoerência da fileira.)
    """
    abrir = (Acao("Abrir o lançador", "", "", ""),)
    if onde is None:
        return Lancador(chave=item.chave, nome=item.nome, selo="nao_sei",
                        jogos="—", diz=DIZ_SEM_FONTE, acoes=abrir)
    if not onde:
        return Lancador(chave=item.chave, nome=item.nome, selo="off",
                        jogos="—", diz=DIZ_NAO_ACHEI, acoes=abrir)
    return Lancador(chave=item.chave, nome=item.nome, selo="nao_sei",
                    jogos="—", diz=DIZ_ACHEI.format(onde=_e(onde)),
                    acoes=abrir, presente=True)


def cartoes(lida: Leitura | None) -> list[Lancador]:
    """Os seis cartões: o que tem censo, e os cinco que só têm presença."""
    onde_estao = dict(lida.onde_estao) if lida is not None else {}
    fora = [cartao_da_steam(lida)]
    for item in SEM_FONTE:
        fora.append(cartao_sem_censo(item, onde_estao.get(item.chave)))
    return fora


@dataclass
class Quadro:
    """Tudo o que a aba mostra: os cartões e a contagem do topo."""

    lancadores: list[Lancador] = field(default_factory=list)

    @property
    def achados(self) -> int:
        """Quantos lançadores o produto ACHOU nesta máquina.

        LIA O SELO, E O SELO É OUTRA PERGUNTA. Até 02/09 esta conta somava
        `ok` e `warn` — o que respondia *"em quantos lançadores eu sei dizer se
        os controles chegam?"*, e não *"quantos lançadores estão aqui?"*, que é
        o que a palavra **encontrados** promete a quem lê a tela. Enquanto o
        produto não olhava a presença, as duas contas davam o mesmo número e a
        diferença ficou escondida; assim que ele passou a olhar, um lançador
        instalado cujo interior ele não lê passaria a ser "não encontrado" com
        o cartão dizendo *"achei este lançador aqui"*, na mesma tela.

        Agora ela soma `presente`, que é a resposta da pergunta que o rótulo faz.
        """
        return sum(1 for x in self.lancadores if x.presente)

    @property
    def impedidos(self) -> int:
        return sum(1 for x in self.lancadores if x.selo == "warn")

    def valores(self) -> dict[str, str]:
        """O pacote inteiro de valores da aba."""
        fora: dict[str, str] = {"lanc-conta": conta_html(self.achados, self.impedidos)}
        for lanc in self.lancadores:
            fora.update(valores_do_cartao(lanc))
        return fora


__all__ = [
    "AINDA_LENDO",
    "A_STEAM",
    "CLASSE_DA_GRADE",
    "DIZ_ACHEI",
    "DIZ_NAO_ACHEI",
    "DIZ_SEM_FONTE",
    "MOLDURA",
    "PROCURADOS",
    "SELETOR_DA_GRADE",
    "SELOS",
    "SEM_FONTE",
    "SEM_LISTA",
    "STEAM",
    "SUFIXOS",
    "SUFIXO_DA_LISTA",
    "Acao",  # (noqa-acento) nome de CLASSE — identificador Python não leva acento
    "JogoNaLista",
    "Lancador",
    "Leitura",
    "Quadro",
    "SemCenso",
    "acao_html",
    "acoes_html",
    "carimbo_da_steam",
    "carimbo_html",
    "cartao_da_steam",
    "cartao_sem_censo",
    "cartoes",
    "cartoes_html",
    "conta_html",
    "linhas_de_jogos",
    "lista_de_jogos",
    "selo_html",
    "um_cartao",
    "valores_do_cartao",
]
